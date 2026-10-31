"""Seed-first, then union-pool constructive fleet minimisation.

Pipeline:
 1. One deterministic cap-sized Walker constellation; one cached fast
    propagation pass. Correct off-nadir geometry via sim.visible (angle
    between -sat and target-sat), conservative margin/interior buffer.
 2. Immediately a chronological-greedy cap seed is stored as best-so-far
    (never empty/1-action); it is returned unchanged if nothing smaller
    verifies.
 3. EDF scheduling and reschedule-aware deep pruning on cached candidates
    give the incumbent.
 4. Only after the seed: a union pool is built from 2-3 FULL-cap Walker
    variants (different plane/phase layout and one alternate inclination
    and altitude), each propagated once with cached fast propagation and
    deduplicated. No sampled representative subset, no pre-seed screening.
 5. Constructive minimisation: from an empty fleet, shortlist pool orbits
    by coverage of currently violated edge-inclusive gap intervals, judge
    only the top few with the actual slew-safe cached scheduler's verified
    gap violation, and add the best orbit; stop when feasible or when the
    fleet reaches incumbent size minus 1.
 6. Joint compression on the incumbent: 2-for-1 swaps (remove 2, add 1
    pool orbit) and swap-then-prune, accepted only after a full cached
    re-schedule verifies every revisit gap including mission edges plus
    a final slew audit.
All insertions check slew/settling/non-overlap/battery-cap against
predecessor/successor (no displacement repair, no unchecked re-insertion).
A hard internal deadline (~70% of time_limit_s) is checked inside every
costly loop (candidate, construction, swap and battery-cap loops use the
cached action cap). All choices derive from `world`; nothing mission
specific is hardcoded.
"""
import bisect
import math
import time

import numpy as np
import sim

MARGIN_S = 0.5 * 3600.0
PRUNE_MARGIN_S = 0.10 * 3600.0
VIS_MARGIN_DEG = 0.7
BUFFER_STEPS = 3  # interior grid steps kept clear at each window edge


def _constellation(n, alt_m, inc_deg):
    planes = max(1, int(round(math.sqrt(n))))
    base, extra = divmod(n, planes)
    states, elems = [], []
    for p in range(planes):
        per = base + (1 if p < extra else 0)
        for s in range(per):
            raan = 360.0 * p / planes
            ma = 360.0 * s / max(per, 1) + 360.0 * p / max(n, 1)
            elems.append((alt_m, inc_deg, raan, ma))
            states.append(sim.state_from_elements(alt_m, inc_deg, raan, ma))
    return states, elems


def _walker(n, alt_m, inc_deg, planes, raan_off=0.0, ma_off=0.0):
    planes = max(1, min(int(planes), int(n)))
    base, extra = divmod(int(n), planes)
    states, elems = [], []
    for p in range(planes):
        per = base + (1 if p < extra else 0)
        for s in range(per):
            raan = (360.0 * p / planes + raan_off) % 360.0
            ma = (360.0 * s / max(per, 1) + 360.0 * p / max(int(n), 1)
                  + ma_off) % 360.0
            elems.append((float(alt_m), float(inc_deg), raan, ma))
            states.append(sim.state_from_elements(alt_m, inc_deg, raan, ma))
    return states, elems


def _elem_key(el):
    return (round(float(el[0]) / 5000.0), round(float(el[1]) * 2.0),
            round((float(el[2]) % 360.0) / 2.0),
            round((float(el[3]) % 360.0) / 2.0))


def _violated_intervals(world, midpoints):
    """Edge-inclusive violated gap intervals (mission start/end counted)."""
    req = [float(t['expected_revisit_period_hours']) * 3600.0
           for t in world['targets']]
    H = float(world['horizon_s'])
    out = []
    for j in range(len(req)):
        pts = [0.0] + sorted(midpoints.get(j, [])) + [H]
        for a, b in zip(pts, pts[1:]):
            if b - a > req[j] - PRUNE_MARGIN_S + 1e-9:
                out.append((j, a, b, (b - a) - (req[j] - PRUNE_MARGIN_S)))
    return out


def _violation_key(world, midpoints, n_actions=0):
    gaps, _m, _w = _gap_stats(world, midpoints)
    req = [float(t['expected_revisit_period_hours']) * 3600.0
           for t in world['targets']]
    missing = sum(1 for j, g in enumerate(gaps)
                  if g > req[j] - PRUNE_MARGIN_S + 1e-9)
    total = sum(max(0.0, gaps[j] - (req[j] - PRUNE_MARGIN_S))
                for j in range(len(gaps)))
    worst = max([gaps[j] - req[j] for j in range(len(gaps))] + [0.0])
    return (missing, total, worst, -int(n_actions))


def _slew_audit(world, fleet):
    """Independent final slew audit: per satellite, time-sorted actions
    must not overlap and must satisfy slew + settling separation, and the
    cached battery action-cap must not be exceeded."""
    settle = float(world['model']['attitude_model']['settling_time_sec'])
    for i, lst in fleet.sched.items():
        if fleet.count.get(i, 0) > fleet.action_cap:
            return False
        ordered = sorted(lst, key=lambda q: q[0])
        for prev, cur in zip(ordered, ordered[1:]):
            if prev[1] > cur[0] + 1e-9:
                return False
            dot = max(-1.0, min(1.0, sum(prev[4][k] * cur[4][k]
                                         for k in range(3))))
            need = sim.slew_time(math.degrees(math.acos(dot)), world) + settle
            if cur[0] - prev[1] < need - 1e-9:
                return False
    return True


def _shortlist(world, pool_by_sat, intervals, excluded, top_k, deadline_t):
    """Rank pool orbits by coverage of violated edge-inclusive intervals.

    Score: number of distinct violated intervals containing at least one
    cached candidate midpoint of this orbit, plus a small tie-break on
    total candidates inside violated intervals. Proxy only shortlists;
    the scheduler judges."""
    by_tgt = {}
    for (j, a, b, _ex) in intervals:
        by_tgt.setdefault(j, []).append((a, b))
    scored = []
    for sat, cands in enumerate(pool_by_sat):
        if sat in excluded or time.time() > deadline_t:
            continue
        covered = set()
        hits = 0
        for c in cands:
            ivs = by_tgt.get(c[4])
            if not ivs:
                continue
            for (a, b) in ivs:
                if a + 30.0 < c[0] < b - 30.0:
                    covered.add((c[4], a, b)); hits += 1; break
        if covered:
            scored.append((len(covered), hits, -sat, sat))
    scored.sort(reverse=True)
    return [s[3] for s in scored[:top_k]]


def _choose_alt(world, preferred_m):
    lo = float(world['model']['min_altitude_m'])
    hi = float(world['model']['max_altitude_m'])
    alt = min(max(preferred_m, lo + 40000.0), hi - 40000.0)
    if hi - lo < 80000.0:
        alt = 0.5 * (lo + hi)
    st = sim.state_from_elements(alt, 55.0, 0.0, 0.0)
    peri, apo = sim.orbit_altitudes(st)
    if peri < lo + 5000.0 or apo > hi - 5000.0:
        alt = 0.5 * (lo + hi)
    return alt


def _action_cap(world):
    """Conservative per-satellite action cap from cached battery model."""
    try:
        res = world['model']['resource_model']
        sen = world['model']['sensor']
        cap_wh = float(res['battery_capacity_wh'])
        init_wh = float(res['initial_battery_wh'])
        obs_w = float(sen['obs_discharge_rate_w'])
        charge_w = float(res['sunlight_charge_rate_w'])
        # Assume ~60% sunlit charging over 48h roughly offsets idle load;
        # budget imaging energy from initial + a fraction of capacity.
        usable = max(init_wh, 0.5 * cap_wh)
        per_photo_wh = max(obs_w, 1.0) * 60.0 / 3600.0  # ~60 s upper photo
        n = int(usable / max(per_photo_wh, 1e-6))
        return max(40, min(160, n))
    except Exception:
        return 100


def _build_candidates(world, elems, ecef_tracks, deadline_t):
    """Cached opportunities from the single fast-propagation pass.

    Candidate: (mid, start, end, sat, target, losx, losy, losz, is_center)
    Bounded: at most 3 starts per visibility run, centre preferred.
    """
    ts = world['times']
    H = float(world['horizon_s'])
    rot = world['rot']
    n_sat = len(elems)
    by_target = [[] for _ in world['targets']]
    centre_by_sat = [[] for _ in range(n_sat)]
    all_centre = []
    for i in range(n_sat):
        if time.time() > deadline_t:
            break
        vis = sim.visible(world, ecef_tracks[i], margin_deg=VIS_MARGIN_DEG)
        sat_ecef = ecef_tracks[i]
        for j, t in enumerate(world['targets']):
            dur = float(t['min_duration_sec'])
            need = max(1, int(math.ceil(dur / sim.STEP_S - 1e-9)))
            d = np.diff(np.r_[0, vis[j].astype(int), 0])
            starts_idx = np.where(d == 1)[0]
            ends_idx = np.where(d == -1)[0]
            tgt_ecef = t['ecef']
            for a, b in zip(starts_idx, ends_idx):
                span = int(b - a)
                if span < need + 2 * BUFFER_STEPS:
                    continue
                lo_s = int(a) + BUFFER_STEPS
                hi_s = int(b) - BUFFER_STEPS - need
                if hi_s < lo_s:
                    continue
                centre = (lo_s + hi_s) // 2
                cand_starts = {lo_s, centre, hi_s}
                for s_idx in sorted(cand_starts):
                    s0 = float(ts[s_idx]); e0 = s0 + dur
                    if e0 > H + 1e-9:
                        continue
                    mid = s0 + dur / 2.0
                    mid_idx = min(max(int(round(mid / sim.STEP_S)), 0), len(ts) - 1)
                    tgt_eci = rot[mid_idx].T @ tgt_ecef
                    sat_eci = rot[mid_idx].T @ sat_ecef[mid_idx]
                    los = tgt_eci - sat_eci
                    nrm = float(np.linalg.norm(los))
                    if nrm <= 0:
                        continue
                    los = los / nrm
                    cand = (mid, s0, e0, i, j, float(los[0]), float(los[1]),
                            float(los[2]), s_idx == centre)
                    by_target[j].append(cand)
                    if s_idx == centre:
                        centre_by_sat[i].append(cand)
                        all_centre.append(cand)
    for j in range(len(by_target)):
        by_target[j].sort(key=lambda c: (c[0], c[3]))
    for i in range(n_sat):
        centre_by_sat[i].sort(key=lambda c: (c[1], c[4]))
    all_centre.sort(key=lambda c: (c[1], c[3], c[4]))
    mids_by_target = [[c[0] for c in lst] for lst in by_target]
    return by_target, centre_by_sat, all_centre, mids_by_target


class _Fleet:
    def __init__(self, world, allowed, action_cap):
        self.world = world
        self.allowed = set(allowed)
        self.settle = float(world['model']['attitude_model']['settling_time_sec'])
        self.sched = {i: [] for i in self.allowed}
        self.starts = {i: [] for i in self.allowed}
        self.count = {i: 0 for i in self.allowed}
        self.action_cap = action_cap

    def _slew(self, los_a, los_b):
        dot = max(-1.0, min(1.0, los_a[0]*los_b[0] + los_a[1]*los_b[1] + los_a[2]*los_b[2]))
        return sim.slew_time(math.degrees(math.acos(dot)), self.world)

    def feasible(self, cand):
        _mid, s0, e0, i, _j, lx, ly, lz, _c = cand
        if i not in self.allowed or self.count[i] >= self.action_cap:
            return False
        lst = self.sched[i]; starts = self.starts[i]
        k = bisect.bisect_left(starts, s0)
        los = (lx, ly, lz)
        if k > 0:
            p = lst[k-1]
            if p[1] > s0 + 1e-9 or s0 - p[1] < self._slew(p[4], los) + self.settle - 1e-9:
                return False
        if k < len(lst):
            q = lst[k]
            if e0 > q[0] + 1e-9 or q[0] - e0 < self._slew(los, q[4]) + self.settle - 1e-9:
                return False
        return True

    def insert(self, cand):
        mid, s0, e0, i, j, lx, ly, lz, _c = cand
        k = bisect.bisect_left(self.starts[i], s0)
        self.sched[i].insert(k, [s0, e0, mid, j, (lx, ly, lz)])
        self.starts[i].insert(k, s0)
        self.count[i] += 1

    def actions(self, remap):
        out = []
        for i in sorted(self.sched):
            for s0, e0, _mid, j, _los in self.sched[i]:
                out.append((remap[i], j, float(s0), float(e0)))
        out.sort(key=lambda q: (q[0], q[2], q[1]))
        return out

    def midpoints(self, n_targets):
        mp = {j: [] for j in range(n_targets)}
        for i in self.sched:
            for _s0, _e0, mid, j, _los in self.sched[i]:
                mp[j].append(mid)
        for j in mp:
            mp[j].sort()
        return mp


def _gap_stats(world, midpoints):
    req = [float(t['expected_revisit_period_hours'])*3600.0 for t in world['targets']]
    H = float(world['horizon_s'])
    gaps, missing, worst_excess = [], 0, 0.0
    for j in range(len(world['targets'])):
        pts = [0.0] + sorted(midpoints.get(j, [])) + [H]
        g = max(b-a for a, b in zip(pts, pts[1:]))
        gaps.append(g)
        if g > req[j] + 1e-9:
            missing += 1
        worst_excess = max(worst_excess, g - req[j])
    return gaps, missing, worst_excess


def _score_key(world, midpoints, n_actions):
    gaps, missing, worst_excess = _gap_stats(world, midpoints)
    total = 0.0
    for j, g in enumerate(gaps):
        req = float(world['targets'][j]['expected_revisit_period_hours'])*3600.0
        total += max(0.0, g - req)
    return (missing, total, worst_excess, -n_actions)


def _seed_greedy(world, all_centre, allowed, action_cap, deadline_t):
    """Chronological greedy seed: time-ordered centre candidates, taking a
    photo only if its target has not been photographed recently (spacing
    >= 0.4*requirement), subject to slew/settling/battery-cap checks."""
    fleet = _Fleet(world, allowed, action_cap)
    n_t = len(world['targets'])
    req = [float(t['expected_revisit_period_hours'])*3600.0 for t in world['targets']]
    last = [-1e18] * n_t
    for cand in all_centre:
        if time.time() > deadline_t:
            break
        mid, _s, _e, _i, j = cand[0], cand[1], cand[2], cand[3], cand[4]
        if mid - last[j] < 0.40 * req[j]:
            continue
        if fleet.feasible(cand):
            fleet.insert(cand)
            last[j] = mid
    return fleet


def _repair(world, by_target, mids_by_target, fleet, margin_s, deadline_t):
    n_t = len(world['targets'])
    req = [float(t['expected_revisit_period_hours'])*3600.0 for t in world['targets']]
    H = float(world['horizon_s'])
    ignored = set()
    for _ in range(800):
        if time.time() > deadline_t:
            return
        mp = fleet.midpoints(n_t)
        worst = None
        for j in range(n_t):
            pts = [0.0] + mp[j] + [H]
            for a, b in zip(pts, pts[1:]):
                if (j, round(a), round(b)) in ignored:
                    continue
                excess = (b-a) - (req[j]-margin_s)
                if excess > 0 and (worst is None or excess > worst[0]):
                    worst = (excess, j, a, b)
        if worst is None:
            return
        _ex, j, a, b = worst
        centre = 0.5*(a+b)
        lo = bisect.bisect_right(mids_by_target[j], a+30.0)
        hi = bisect.bisect_left(mids_by_target[j], b-30.0)
        window = by_target[j][lo:hi]
        window = sorted(window, key=lambda c: (abs(c[0]-centre), c[0], c[3]))
        inserted = False
        for cand in window[:80]:
            if fleet.feasible(cand):
                fleet.insert(cand); inserted = True; break
        if not inserted:
            ignored.add((j, round(a), round(b)))


def _deadline_schedule(world, by_target, mids_by_target, allowed, margin_s,
                       deadline_t, action_cap, pick_latest=True):
    fleet = _Fleet(world, allowed, action_cap)
    n_t = len(world['targets'])
    req = [float(t['expected_revisit_period_hours'])*3600.0 for t in world['targets']]
    H = float(world['horizon_s'])
    last = [0.0]*n_t
    blocked = [False]*n_t
    for _ in range(8000):
        if time.time() > deadline_t:
            break
        best_j, best_key = -1, None
        for j in range(n_t):
            if blocked[j]:
                continue
            dl = last[j] + req[j] - margin_s
            if dl >= H:
                continue
            key = (dl, j)
            if best_key is None or key < best_key:
                best_key, best_j = key, j
        if best_j < 0:
            break
        j = best_j
        dl = last[j] + req[j] - margin_s
        mids = mids_by_target[j]; cands = by_target[j]
        lo = bisect.bisect_right(mids, last[j]+30.0)
        hi = bisect.bisect_right(mids, dl)  # candidates with mid <= dl
        pick = None
        idx_range = range(hi-1, lo-1, -1) if pick_latest else range(lo, hi)
        for idx in idx_range:  # latest (or earliest) feasible <= deadline
            if fleet.feasible(cands[idx]):
                pick = cands[idx]; break
        if pick is None:
            # earliest feasible after last (may be past deadline: least late)
            for idx in range(lo, len(cands)):
                if cands[idx][0] >= H:
                    break
                if fleet.feasible(cands[idx]):
                    pick = cands[idx]; break
        if pick is None:
            blocked[j] = True
            continue
        fleet.insert(pick)
        last[j] = pick[0]
    _repair(world, by_target, mids_by_target, fleet, margin_s, deadline_t)
    return fleet


def _sole_coverage(by_target, mids_by_target, window_s=2700.0):
    """Per-satellite count of cached opportunities no other satellite can
    serve within +/-window_s for the same target (from cached candidates)."""
    sole = {}
    for j, cands in enumerate(by_target):
        mids = mids_by_target[j]
        for idx, c in enumerate(cands):
            sat = c[3]
            lo = bisect.bisect_left(mids, c[0] - window_s)
            hi = bisect.bisect_right(mids, c[0] + window_s)
            others = False
            for k in range(lo, hi):
                if cands[k][3] != sat:
                    others = True
                    break
            if not others:
                sole[sat] = sole.get(sat, 0) + 1
    return sole


def _fleet_stats(world, fleet, current):
    """Redundant-photo count and deadline slack per satellite in `fleet`.
    A photo is redundant if deleting it alone keeps its target's gap within
    req-PRUNE_MARGIN; slack sums req - worst neighbouring gap per photo."""
    req = [float(t['expected_revisit_period_hours']) * 3600.0
           for t in world['targets']]
    H = float(world['horizon_s'])
    per_target = {j: [] for j in range(len(req))}
    for i in current:
        for _s0, _e0, mid, j, _los in fleet.sched.get(i, []):
            per_target[j].append((mid, i))
    redundant = {i: 0 for i in current}
    slack = {i: 0.0 for i in current}
    for j, lst in per_target.items():
        lst.sort()
        pts = [(0.0, -1)] + lst + [(H, -1)]
        for k in range(1, len(pts) - 1):
            mid, sat = pts[k]
            prev_m, next_m = pts[k - 1][0], pts[k + 1][0]
            if next_m - prev_m <= req[j] - PRUNE_MARGIN_S + 1e-9:
                redundant[sat] += 1
            slack[sat] += req[j] - max(mid - prev_m, next_m - mid)
    return redundant, slack


def _ranked(world, fleet, current, sole, mode):
    redundant, slack = _fleet_stats(world, fleet, current)
    counts = {i: fleet.count.get(i, 0) for i in current}
    if mode == 0:  # ascending sole-coverage, then least used
        return sorted(current, key=lambda i: (sole.get(i, 0), counts[i], i))
    if mode == 1:  # descending redundancy, then ascending sole-coverage
        return sorted(current,
                      key=lambda i: (-redundant[i], sole.get(i, 0), i))
    if mode == 2:  # descending deadline slack, then ascending sole-coverage
        return sorted(current,
                      key=lambda i: (-slack[i], sole.get(i, 0), i))
    # mode 3: deterministic rotation of the mode-0 ordering
    base = sorted(current, key=lambda i: (sole.get(i, 0), counts[i], i))
    if len(base) > 2:
        r = max(1, len(base) // 3)
        base = base[r:] + base[:r]
    return base


def _verify_feasible(world, fleet):
    gaps, missing, _w = _gap_stats(world, fleet.midpoints(len(world['targets'])))
    if missing != 0:
        return False
    req = [float(t['expected_revisit_period_hours']) * 3600.0
           for t in world['targets']]
    return all(gaps[k] <= req[k] - PRUNE_MARGIN_S + 1e-9
               for k in range(len(req)))


def solve(world, time_limit_s):
    t_start = time.time()
    tl = float(time_limit_s)
    hard_deadline = t_start + 0.70 * tl          # hard internal deadline (~70%)
    return_deadline = t_start + max(20.0, tl - 20.0)
    deadline = min(hard_deadline, return_deadline)
    cap = int(world['cap'])
    n_t = len(world['targets'])
    action_cap = _action_cap(world)
    alt = _choose_alt(world, 700e3)

    # --- Stage 1: cheap candidates, single fast-propagation pass ---
    states, elems = _constellation(cap, alt, 55.0)
    ecef_tracks = sim.fast_positions(world, elems)  # cached once
    by_target, centre_by_sat, all_centre, mids_by_target = _build_candidates(
        world, elems, ecef_tracks, deadline)
    allowed = list(range(cap))

    # --- Stage 2: unconditional chronological-greedy seed (best-so-far) ---
    best_fleet = _seed_greedy(world, all_centre, allowed, action_cap, deadline)
    best_states = list(states)
    best_allowed = list(allowed)
    best_key = _score_key(world, best_fleet.midpoints(n_t),
                          sum(best_fleet.count.values()))
    _g, best_missing, _w = _gap_stats(world, best_fleet.midpoints(n_t))

    def consider(fleet, cand_states, cand_allowed):
        nonlocal best_fleet, best_states, best_allowed, best_key, best_missing
        key = _score_key(world, fleet.midpoints(n_t), sum(fleet.count.values()))
        if key < best_key:
            best_fleet, best_key = fleet, key
            best_states, best_allowed = list(cand_states), list(cand_allowed)
            _gg, best_missing, _ww = _gap_stats(world, fleet.midpoints(n_t))
            return True
        return False

    # --- Stage 3: EDF + repair on cached candidates (leftover budget) ---
    if time.time() < deadline:
        edf = _deadline_schedule(world, by_target, mids_by_target, allowed,
                                 MARGIN_S, deadline, action_cap)
        consider(edf, states, allowed)

    # --- Stage 4: reschedule-aware deep pruning (cached candidates only) ---
    # No re-propagation here: every trial reuses by_target/mids_by_target.
    _g, missing, _w = _gap_stats(world, best_fleet.midpoints(n_t))
    if missing == 0 and time.time() < deadline:
        sole = _sole_coverage(by_target, mids_by_target)
        current = list(best_allowed)
        cur_fleet = best_fleet
        attempts = [0]
        max_attempts = 240

        def try_reschedule(trial_allowed):
            """Full EDF re-schedule of trial fleet + full gap verification.
            Returns a verified fleet or None. Never photo-deletion."""
            if time.time() > deadline or attempts[0] >= max_attempts:
                return None
            attempts[0] += 1
            variants = [(0.30 * 3600.0, True)]
            tf = _deadline_schedule(world, by_target, mids_by_target,
                                    trial_allowed, variants[0][0], deadline,
                                    action_cap, pick_latest=True)
            if _verify_feasible(world, tf):
                return tf
            _tg, tmiss, _tw = _gap_stats(world, tf.midpoints(n_t))
            if tmiss <= 3:  # near miss: try other deterministic variants
                for margin_s, latest in [(MARGIN_S, True),
                                         (0.12 * 3600.0, True),
                                         (0.30 * 3600.0, False)]:
                    if time.time() > deadline:
                        return None
                    tf = _deadline_schedule(world, by_target, mids_by_target,
                                            trial_allowed, margin_s, deadline,
                                            action_cap, pick_latest=latest)
                    if _verify_feasible(world, tf):
                        return tf
            return None

        progress = True
        while progress and len(current) > 1 and time.time() < deadline:
            progress = False
            # Single removals under 4 deterministic orderings.
            for mode in (0, 1, 2, 3):
                while len(current) > 1 and time.time() < deadline:
                    ranked = _ranked(world, cur_fleet, current, sole, mode)
                    accepted = False
                    for cand_sat in ranked:
                        if attempts[0] >= max_attempts or time.time() > deadline:
                            break
                        trial = [i for i in current if i != cand_sat]
                        tf = try_reschedule(trial)
                        if tf is not None:
                            current, cur_fleet = trial, tf
                            accepted = True
                            progress = True
                            break  # re-rank after each accepted removal
                    if not accepted:
                        break  # stalled under this ordering; try next
                if attempts[0] >= max_attempts:
                    break
            # Pair removal only after all single-removal orderings stall.
            if not progress and len(current) > 2 and time.time() < deadline:
                ranked = _ranked(world, cur_fleet, current, sole, 0)
                pairs = []
                for a_idx in range(min(3, len(ranked))):
                    for b_idx in range(a_idx + 1, min(4, len(ranked))):
                        pairs.append((ranked[a_idx], ranked[b_idx]))
                for pa, pb in pairs:
                    if attempts[0] >= max_attempts or time.time() > deadline:
                        break
                    trial = [i for i in current if i not in (pa, pb)]
                    if len(trial) < 1:
                        continue
                    tf = try_reschedule(trial)
                    if tf is not None:
                        current, cur_fleet = trial, tf
                        progress = True
                        break
        if len(current) < len(best_allowed):
            keep = set(current)
            best_states = [s for i, s in enumerate(best_states) if i in keep]
            best_allowed = list(current)
            best_fleet = cur_fleet

    # --- Stage 5: union pool (only AFTER seed/incumbent exist) ---
    # --- Stage 6: constructive minimisation + joint compression ---
    try:
        _gb, _best_miss0, _wb = _gap_stats(
            world, best_fleet.midpoints(n_t))
        incumbent_feasible = (_best_miss0 == 0)
        target_limit = (len(best_allowed) - 1) if incumbent_feasible else cap
        if time.time() < deadline and target_limit >= 1:
            planes0 = max(1, int(round(math.sqrt(cap))))
            alt2 = _choose_alt(world, alt + 80000.0)
            variants = [elems]
            variants.append(_walker(cap, alt, 55.0,
                                    min(cap, planes0 + 1),
                                    raan_off=180.0 / max(planes0 + 1, 1),
                                    ma_off=37.0)[1])
            variants.append(_walker(cap, alt2, 63.0,
                                    max(1, planes0 - 1) if planes0 > 1 else 2,
                                    raan_off=53.0, ma_off=71.0)[1])
            pool_elems, pool_states, key_to_pool = [], [], {}
            for var in variants:  # 2-3 FULL-cap Walker variants
                for el in var:
                    if time.time() > deadline:
                        break
                    k = _elem_key(el)
                    if k not in key_to_pool:
                        key_to_pool[k] = len(pool_elems)
                        pool_elems.append(el)
                        pool_states.append(
                            sim.state_from_elements(el[0], el[1], el[2], el[3]))
            orig_to_pool = {}
            for oi, el in enumerate(elems):
                if _elem_key(el) in key_to_pool:
                    orig_to_pool[oi] = key_to_pool[_elem_key(el)]
            # Cached fast propagation once for the whole union pool.
            ecef_pool = sim.fast_positions(world, pool_elems)
            by_t_p, _cbs_p, _ac_p, mids_p = _build_candidates(
                world, pool_elems, ecef_pool, deadline)
            pool_by_sat = [[] for _ in pool_elems]
            for _j, _lst in enumerate(by_t_p):
                for _c in _lst:
                    pool_by_sat[_c[3]].append(_c)
            joint_budget = [0]

            def schedule_pool(trial_ids):
                if (time.time() > deadline or joint_budget[0] >= 90
                        or not trial_ids):
                    return None
                joint_budget[0] += 1
                return _deadline_schedule(
                    world, by_t_p, mids_p, list(trial_ids),
                    0.30 * 3600.0, deadline, action_cap, pick_latest=True)

            cur_ids, cur_fleet_p = None, None
            incumbent_pool_ids = [orig_to_pool[i] for i in best_allowed
                                  if i in orig_to_pool]
            if (incumbent_feasible
                    and len(incumbent_pool_ids) == len(best_allowed)):
                tf0 = schedule_pool(incumbent_pool_ids)
                if (tf0 is not None and _verify_feasible(world, tf0)
                        and _slew_audit(world, tf0)):
                    cur_ids, cur_fleet_p = list(incumbent_pool_ids), tf0
            # Constructive bottom-up minimisation from an empty fleet.
            selected, sel_fleet = [], None
            empty_mp = {j: [] for j in range(n_t)}
            cur_key = _violation_key(world, empty_mp, 0)
            while (len(selected) < target_limit
                   and time.time() < deadline):
                mp_now = (sel_fleet.midpoints(n_t) if sel_fleet is not None
                          else empty_mp)
                intervals = _violated_intervals(world, mp_now)
                if not intervals:
                    break
                short = _shortlist(world, pool_by_sat, intervals,
                                   set(selected), 4, deadline)
                if not short:
                    break
                best_trial, best_oid, best_tkey = None, None, None
                for oid in short:
                    if time.time() > deadline:
                        break
                    tf = schedule_pool(selected + [oid])
                    if tf is None:
                        continue
                    tkey = _violation_key(
                        world, tf.midpoints(n_t),
                        sum(tf.count.values()))
                    if best_tkey is None or tkey < best_tkey:
                        best_trial, best_oid, best_tkey = tf, oid, tkey
                if best_trial is None or not (best_tkey < cur_key):
                    break
                selected.append(best_oid)
                sel_fleet, cur_key = best_trial, best_tkey
                if (_verify_feasible(world, sel_fleet)
                        and _slew_audit(world, sel_fleet)):
                    break
            if (sel_fleet is not None and selected
                    and _verify_feasible(world, sel_fleet)
                    and _slew_audit(world, sel_fleet)
                    and len(selected) <= target_limit
                    and (not incumbent_feasible
                         or len(selected) < len(best_allowed))):
                cur_ids, cur_fleet_p = list(selected), sel_fleet
            # Joint compression: 2-for-1 and swap-then-prune.
            if cur_ids is not None and cur_fleet_p is not None:
                improved = True
                while (improved and len(cur_ids) > 1
                       and time.time() < deadline
                       and joint_budget[0] < 90):
                    improved = False
                    ranked_cur = _ranked(world, cur_fleet_p, cur_ids, {}, 0)
                    # 2-for-1 swaps.
                    pairs = []
                    top_r = ranked_cur[:5]
                    for _a in range(len(top_r)):
                        for _b in range(_a + 1, len(top_r)):
                            pairs.append((top_r[_a], top_r[_b]))
                    for pa, pb in pairs:
                        if improved or time.time() > deadline:
                            break
                        base = [i for i in cur_ids if i not in (pa, pb)]
                        bf = schedule_pool(base)
                        if bf is None:
                            continue
                        ivs = _violated_intervals(
                            world, bf.midpoints(n_t))
                        if not ivs:
                            continue
                        for oid in _shortlist(world, pool_by_sat, ivs,
                                              set(base), 3, deadline):
                            tf = schedule_pool(base + [oid])
                            if (tf is not None
                                    and _verify_feasible(world, tf)
                                    and _slew_audit(world, tf)):
                                cur_ids = base + [oid]
                                cur_fleet_p = tf
                                improved = True
                                break
                    if improved:
                        continue
                    # Swap-then-prune: 1-for-1 swap, then one removal.
                    for removed in ranked_cur[:4]:
                        if improved or time.time() > deadline:
                            break
                        base = [i for i in cur_ids if i != removed]
                        bf = schedule_pool(base)
                        if bf is None:
                            continue
                        ivs = _violated_intervals(
                            world, bf.midpoints(n_t))
                        cand_oids = (_shortlist(world, pool_by_sat, ivs,
                                                set(base), 2, deadline)
                                     if ivs else [])
                        for oid in cand_oids:
                            if improved:
                                break
                            swapped = base + [oid]
                            sf = schedule_pool(swapped)
                            if (sf is None
                                    or not _verify_feasible(world, sf)
                                    or not _slew_audit(world, sf)):
                                continue
                            ranked_sw = _ranked(world, sf, swapped, {}, 0)
                            for extra in ranked_sw[:4]:
                                if extra == oid:
                                    continue
                                trial = [i for i in swapped if i != extra]
                                tf = schedule_pool(trial)
                                if (tf is not None
                                        and _verify_feasible(world, tf)
                                        and _slew_audit(world, tf)):
                                    cur_ids, cur_fleet_p = trial, tf
                                    improved = True
                                    break
            if (cur_ids is not None and cur_fleet_p is not None
                    and len(cur_ids) < len(best_allowed)
                    and _verify_feasible(world, cur_fleet_p)
                    and _slew_audit(world, cur_fleet_p)):
                best_states = [pool_states[i] for i in cur_ids]
                best_allowed = list(cur_ids)
                best_fleet = cur_fleet_p
    except Exception:
        pass  # verified seed/incumbent remains the fallback

    # Final slew audit before acceptance; fall back to seed if it fails.
    if not _slew_audit(world, best_fleet):
        best_fleet = _seed_greedy(world, all_centre, list(range(cap)),
                                  action_cap, deadline)
        best_states = list(states)
        best_allowed = list(range(cap))
    remap = {old: new for new, old in enumerate(best_allowed)}
    actions = best_fleet.actions(remap)
    if not actions:  # last resort: seed actions (never 0/1-action guard by design)
        actions = _seed_greedy(world, all_centre, best_allowed, action_cap,
                               deadline).actions(remap)
    if not actions and all_centre:
        c = all_centre[0]
        if c[3] in remap:
            actions = [(remap[c[3]], c[4], float(c[1]), float(c[2]))]
    return {'satellites': best_states, 'actions': actions}
