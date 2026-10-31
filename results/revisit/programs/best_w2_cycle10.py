"""Geometry-diverse constructive growth constellation (cycle-10).

Fork of the cycle-9 window-flexible slew-aware program. Order in solve():
 1. Build and internally verify a cap-sized Walker seed; store as best-so-far
    before any geometry search (seed-first, never-empty return).
 2. One fast-propagation pass caches, per visibility window, a small
    deduplicated set of interior candidate instants; no exact propagation
    anywhere in solve() (cached fast propagation only, reused throughout).
 3. Score at most 4 geometry-diverse Walker families (varying plane count /
    satellites-per-plane distribution, Walker phasing factor and RAAN
    offset, one inclination offset and one altitude offset, all derived
    from world cap/requirements) at a reduced fleet size by the actual
    slew-audited scheduler's total edge-inclusive requirement-normalised
    gap violation; keep only the best 1-2 families.
 4. Grow a fleet bottom-up from the kept families' cached candidates:
    repeatedly add the single satellite whose full slew-audited cached
    re-schedule most reduces total gap violation, stopping as soon as
    every target meets its requirement including mission edges.
 5. Verified pruning (singles, then pairs) of the smaller of grown/seed
    fleets; acceptance only after full cached re-schedule plus the
    scheduler's final slew/settling/battery audit.
Hard internal deadline near 70% of time_limit_s (with earlier phase
sub-deadlines) is checked inside every costly loop; on expiry the best
verified non-empty plan is returned.
All parameters derive from world cap/requirements/duration.
"""
import math
import time
import bisect

import numpy as np
import sim


# ---------------------------------------------------------------- helpers
def _clip(v, lo, hi):
    return float(min(max(v, lo), hi))


def _walker_elements(n, alt_m, inc_deg):
    """Uneven-plane Walker-like elements: list of (alt, inc, raan, mean_anom)."""
    n = int(max(1, n))
    planes = max(1, int(round(math.sqrt(n))))
    base, rem = divmod(n, planes)
    els = []
    for p in range(planes):
        cnt = base + (1 if p < rem else 0)
        if cnt == 0:
            continue
        raan = 360.0 * p / planes
        for s in range(cnt):
            ma = 360.0 * s / cnt + 360.0 * p / max(n, 1)
            els.append((float(alt_m), float(inc_deg), raan % 360.0, ma % 360.0))
    return els


def _walker_family(n, alt_m, inc_deg, planes, phase, raan_offset_deg):
    """Walker family with explicit plane count/distribution, phasing
    factor F and RAAN offset. Returns (elements, plane_id_per_element)."""
    n = int(max(1, n)); planes = int(max(1, min(planes, n)))
    base, rem = divmod(n, planes)
    els = []; plane_ids = []
    for p in range(planes):
        cnt = base + (1 if p < rem else 0)
        if cnt == 0:
            continue
        raan = float(raan_offset_deg) + 360.0 * p / planes
        for s in range(cnt):
            ma = 360.0 * s / cnt + float(phase) * 360.0 * p / max(n, 1)
            els.append((float(alt_m), float(inc_deg), raan % 360.0, ma % 360.0))
            plane_ids.append(p)
    return els, plane_ids


def _gap_violation(gaps, req_true):
    """Total edge-inclusive requirement-normalised gap violation."""
    g = np.asarray(gaps, float); r = np.asarray(req_true, float)
    return float(np.sum(np.maximum(0.0, g / np.maximum(r, 1e-9) - 1.0)))


def _state(el, world):
    alt, inc, raan, ma = el
    lo = world['model']['min_altitude_m']
    hi = world['model']['max_altitude_m']
    for _ in range(8):
        st = sim.state_from_elements(alt, inc, raan, ma)
        pa, aa = sim.orbit_altitudes(st)
        if pa >= lo + 2000.0 and aa <= hi - 2000.0:
            return st
        if pa < lo + 2000.0:
            alt += 8000.0
        if aa > hi - 2000.0:
            alt -= 8000.0
        alt = _clip(alt, lo + 5000.0, hi - 5000.0)
    return sim.state_from_elements(_clip(alt, lo + 5000.0, hi - 5000.0), inc, raan, ma)


# ---------------------------------------------------------------- candidates
class Cand:
    __slots__ = ('sat', 'tgt', 'start', 'end', 'mid', 'los', 'win_start', 'win_end')

    def __init__(self, sat, tgt, start, end, mid, los, win_start=0.0, win_end=0.0):
        self.sat = sat; self.tgt = tgt; self.start = start
        self.end = end; self.mid = mid; self.los = los
        self.win_start = win_start; self.win_end = win_end


def _visible_mask(world, ecef_track, margin_deg, range_margin_m):
    """Vectorised (J,T) visibility with safety margins."""
    sen = world['model']['sensor']
    tg = world['targets']
    tpos = np.array([t['ecef'] for t in tg], float)          # (J,3)
    up = np.array([[math.cos(math.radians(t['latitude_deg'])) * math.cos(math.radians(t['longitude_deg'])),
                    math.cos(math.radians(t['latitude_deg'])) * math.sin(math.radians(t['longitude_deg'])),
                    math.sin(math.radians(t['latitude_deg']))] for t in tg], float)
    los = ecef_track[None, :, :] - tpos[:, None, :]          # sat - target (J,T,3)
    rng = np.linalg.norm(los, axis=2)
    rng_safe = np.maximum(rng, 1.0)
    elev = np.degrees(np.arcsin(np.clip(np.einsum('jti,ji->jt', los, up) / rng_safe, -1, 1)))
    sat_norm = np.linalg.norm(ecef_track, axis=1)            # (T,)
    # Off-nadir: angle between nadir (-sat_hat) and line-of-sight
    # (target - sat) = -los. cos = (-sat) . (target-sat) / (|sat|*rng)
    #     = sat . los / (|sat|*rng).  (Cycle-2 bug used -sat . los.)
    cos_off = np.einsum('ti,jti->jt', ecef_track, los) / (sat_norm[None, :] * rng_safe)
    offn = np.degrees(np.arccos(np.clip(cos_off, -1, 1)))
    min_el = np.array([t['min_elevation_deg'] for t in tg], float)[:, None]
    max_rng = np.minimum(np.array([t['max_slant_range_m'] for t in tg], float),
                         float(sen['max_range_m']))[:, None]
    return ((elev >= min_el + margin_deg) & (rng <= max_rng - range_margin_m)
            & (offn <= float(sen['max_off_nadir_angle_deg']) - margin_deg))


def _candidates_from_track(world, sat_idx, ecef_track, margin_deg, buffer_steps, deadline=None):
    """Multiple interior instants per visibility window (buffered start,
    quartiles, buffered end), deduplicated and capped at 5 per window.
    LOS (ECI unit) is recomputed at each instant's midpoint. Each Cand
    records its window bounds so neighbours can be time-shifted only
    within their own window."""
    vis = _visible_mask(world, ecef_track, margin_deg, 3000.0 if margin_deg > 0.5 else 500.0)
    # Sanity gate: a real LEO track must see many target-time cells. If the
    # hand-rolled mask yields zero / implausibly few, rebuild with the
    # sim-provided helper (correct off-nadir) instead of scheduling empty.
    if int(vis.sum()) < len(world['targets']):
        try:
            vis_sim = sim.visible(world, ecef_track, margin_deg=1e-3)
            if int(vis_sim.sum()) > int(vis.sum()):
                vis = vis_sim
        except Exception:
            pass
    ts = world['times']; H = world['horizon_s']; rot = world['rot']
    out = []
    # interior instant fractions derived from the window itself
    fracs = (0.0, 0.25, 0.5, 0.75, 1.0)
    for j, t in enumerate(world['targets']):
        if deadline is not None and (j & 3) == 0 and time.time() > deadline:
            break
        dur = float(t['min_duration_sec'])
        need = int(math.ceil(dur / sim.STEP_S))
        v = vis[j].astype(np.int8)
        d = np.diff(np.r_[0, v, 0])
        starts = np.where(d == 1)[0]; ends = np.where(d == -1)[0]
        for a, b in zip(starts, ends):
            if b - a < need + 2 * buffer_steps:
                continue
            lo_idx = int(a) + int(buffer_steps)
            hi_idx = int(b) - int(buffer_steps) - need  # last viable start idx
            if hi_idx < lo_idx:
                continue
            win_s = float(ts[int(a)]); win_e = float(ts[int(b) - 1]) if int(b) > int(a) else win_s
            seen = set()
            for fr in fracs:
                s_idx = int(round(lo_idx + fr * (hi_idx - lo_idx)))
                if s_idx in seen:
                    continue
                seen.add(s_idx)
                s0 = float(ts[s_idx]); e0 = s0 + dur
                if e0 > H:
                    continue
                mid_idx = int(min(max(s_idx + need // 2, 0), len(ts) - 1))
                los_ecef = t['ecef'] - ecef_track[mid_idx]
                los_eci = rot[mid_idx].T @ los_ecef
                nrm = np.linalg.norm(los_eci)
                if nrm <= 0:
                    continue
                out.append(Cand(sat_idx, j, s0, e0, s0 + dur / 2.0,
                                los_eci / nrm, win_s, win_e))
    return out


# ---------------------------------------------------------------- battery
def _sun_hats(world):
    """Coarse sun unit vectors (ECI) every 1800 s, via brahe through sim.epoch."""
    import brahe
    ts = np.arange(0.0, world['horizon_s'] + 1.0, 1800.0)
    hats = []
    for t in ts:
        sp = np.asarray(brahe.sun_position(sim.epoch(world, float(t))), float)
        hats.append(sp / max(np.linalg.norm(sp), 1.0))
    return ts, np.array(hats)


def _battery_ok(world, eci_tracks, actions_by_sat, sun_ts, sun_hats, margin_frac=0.02):
    """30 s-step battery simulation on (subsampled) ECI tracks; cylindrical shadow."""
    res = world['model']['resource_model']; sen = world['model']['sensor']
    att = world['model']['attitude_model']
    cap = float(res['battery_capacity_wh']); batt0 = float(res['initial_battery_wh'])
    step_idx = np.arange(0, len(world['times']), 3)          # 30 s
    t30 = world['times'][step_idx]
    sun_idx = np.clip((t30 / 1800.0).astype(int), 0, len(sun_hats) - 1)
    sh = sun_hats[sun_idx]
    for i, acts in actions_by_sat.items():
        if i >= len(eci_tracks) or len(eci_tracks) == 0:
            continue
        pos = eci_tracks[i][step_idx]                        # (T30,3)
        proj = np.einsum('ti,ti->t', pos, sh)
        perp = np.linalg.norm(pos - proj[:, None] * sh, axis=1)
        sunlit = ~((proj < 0.0) & (perp < sim.R_EARTH))
        rate = np.where(sunlit, float(res['sunlight_charge_rate_w']), 0.0) - float(res['idle_discharge_rate_w'])
        mids = t30 + 15.0
        for (s0, e0, _j, slew_before) in acts:
            rate = rate - np.where((mids >= s0) & (mids < e0), float(sen['obs_discharge_rate_w']), 0.0)
            if slew_before > 0:
                rate = rate - np.where((mids >= s0 - slew_before) & (mids < s0),
                                       float(att['maneuver_discharge_rate_w']), 0.0)
        batt = batt0
        dt_h = 30.0 / 3600.0
        # sequential cap-at-capacity integration
        for r in rate:
            batt = min(cap, batt + float(r) * dt_h)
            if batt < margin_frac * cap:
                return False
    return True


# ---------------------------------------------------------------- scheduler
def _schedule(world, cand_by_sat, sun_data, eci_by_sat, req_eff_h, deadline):
    """Global earliest-deadline scheduler on cached candidates.

    Returns (actions, gaps_h, feasible, battery_ok). actions use local sat
    indices 0..len(cand_by_sat)-1 (cand.sat is remapped by caller if needed).
    """
    targets = world['targets']; J = len(targets); H = world['horizon_s']
    att = world['model']['attitude_model']; settle = float(att['settling_time_sec'])
    req_s = np.array([req_eff_h[j] * 3600.0 for j in range(J)])
    # pool candidates per target: (mid, cand)
    by_tgt = [[] for _ in range(J)]
    for s, clist in enumerate(cand_by_sat):
        for c in clist:
            by_tgt[c.tgt].append(c)
    mids_by = []
    for j in range(J):
        by_tgt[j].sort(key=lambda c: c.mid)
        mids_by.append([c.mid for c in by_tgt[j]])

    chosen = []                       # list of Cand (sat = position in cand_by_sat)
    per_sat = [[] for _ in range(len(cand_by_sat))]   # sorted Cand lists
    last = [0.0] * J

    def _ang(a, b):
        return math.degrees(math.acos(max(-1.0, min(1.0, float(np.dot(a.los, b.los))))))

    def _sep_ok(p, c):
        return c.start - p.end >= sim.slew_time(_ang(p, c), world) + settle + 2.0

    def slew_ok(c):
        lst = per_sat[c.sat]
        starts = [x.start for x in lst]
        k = bisect.bisect_left(starts, c.start)
        if k > 0 and not _sep_ok(lst[k - 1], c):
            return False
        if k < len(lst) and not _sep_ok(c, lst[k]):
            return False
        return True

    def slew_cost(c):
        lst = per_sat[c.sat]
        starts = [x.start for x in lst]
        k = bisect.bisect_left(starts, c.start)
        cost = 0.0
        if k > 0:
            cost += sim.slew_time(_ang(lst[k - 1], c), world) + settle
        if k < len(lst):
            cost += sim.slew_time(_ang(c, lst[k]), world) + settle
        return cost

    # alternative instants of the same window, for slew-safe time-shifting
    alt_map = {}
    for clist in cand_by_sat:
        for c in clist:
            alt_map.setdefault((c.sat, c.tgt, round(float(c.win_start), 1)), []).append(c)
    for v in alt_map.values():
        v.sort(key=lambda c: c.start)

    def accept(c):
        chosen.append(c)
        lst = per_sat[c.sat]
        starts = [x.start for x in lst]
        lst.insert(bisect.bisect_left(starts, c.start), c)
        if c.mid > last[c.tgt]:
            last[c.tgt] = c.mid

    def _pairwise_ok(lst_sorted):
        return all(_sep_ok(lst_sorted[i], lst_sorted[i + 1])
                   for i in range(len(lst_sorted) - 1))

    def try_accept(c):
        """Insert c directly, else bounded slew-safe time-shift repair:
        shift a conflicting neighbour only to another instant of its own
        window; commit only after full pairwise non-overlap/slew/settling
        re-check of the satellite (battery is re-checked in final audit)."""
        if slew_ok(c):
            accept(c); return True
        lst = per_sat[c.sat]
        starts = [x.start for x in lst]
        k = bisect.bisect_left(starts, c.start)
        neigh = []
        if k > 0:
            neigh.append(lst[k - 1])
        if k < len(lst):
            neigh.append(lst[k])
        attempts = 0
        for nb in neigh:
            for alt in alt_map.get((nb.sat, nb.tgt, round(float(nb.win_start), 1)), []):
                if alt is nb or alt.start == nb.start:
                    continue
                attempts += 1
                if attempts > 12 or time.time() > deadline:
                    return False
                new_lst = sorted([x for x in lst if x is not nb] + [alt],
                                 key=lambda x: x.start)
                trial = sorted(new_lst + [c], key=lambda x: x.start)
                if _pairwise_ok(trial):
                    # commit shift (re-checked above), then insert c
                    if nb in chosen:
                        chosen.remove(nb)
                    chosen.append(alt)
                    per_sat[c.sat] = new_lst
                    last[alt.tgt] = max([x.mid for x in chosen if x.tgt == alt.tgt] + [0.0])
                    accept(c)
                    return True
        return False

    def best_pick(idxs, lst_c, ideal_mid):
        """Among slew-feasible instants minimise slew+settling cost plus
        distance to the ideal mid, i.e. maximise post-insertion slack."""
        best_c = None; best_key = None
        for k in idxs:
            if not (0 <= k < len(lst_c)):
                continue
            c = lst_c[k]
            if not slew_ok(c):
                continue
            key = slew_cost(c) + 0.05 * abs(c.mid - ideal_mid)
            if best_key is None or key < best_key:
                best_key = key; best_c = c
        return best_c

    guard = 0
    while guard < 900:
        guard += 1
        if time.time() > deadline:
            break
        # targets whose final boundary is already satisfied need no more photos
        pending = [j for j in range(J) if last[j] < H - req_s[j] + 60.0]
        if not pending:
            break
        pending.sort(key=lambda j: last[j] + req_s[j])   # earliest deadline first
        progressed = False
        for j in pending:
            dl = last[j] + req_s[j]
            lst = by_tgt[j]; mids = mids_by[j]
            lo = bisect.bisect_left(mids, last[j] + 0.28 * req_s[j])
            hi = bisect.bisect_right(mids, dl - 300.0)
            # window-flexible: choose instant by slew/slack cost near the
            # latest comfortable time before the deadline
            pick = best_pick(range(max(lo, hi - 40), hi), lst, dl - 300.0)
            if pick is None and hi > lo:
                pick = best_pick(range(lo, min(hi, lo + 40)), lst, dl - 300.0)
            if pick is None:
                k0 = bisect.bisect_left(mids, last[j] + 60.0)
                pick = best_pick(range(k0, min(len(lst), k0 + 40)), lst,
                                 last[j] + 0.5 * req_s[j])
            if pick is not None:
                if try_accept(pick):
                    progressed = True; break
            else:
                # bounded time-shift repair on a near-deadline instant
                for k in range(max(lo, hi - 10), hi):
                    if 0 <= k < len(lst) and try_accept(lst[k]):
                        progressed = True; break
                if progressed:
                    break
        if not progressed:
            break

    # gap repair: insert candidates into any remaining over-requirement gap
    for _ in range(250):
        if time.time() > deadline:
            break
        mids_t = [sorted(c.mid for c in chosen if c.tgt == j) for j in range(J)]
        worst = None
        for j in range(J):
            pts = [0.0] + mids_t[j] + [H]
            for a, b in zip(pts, pts[1:]):
                # largest requirement-normalised edge-inclusive gap
                if b - a > req_s[j] and (worst is None or (b - a) / req_s[j] > worst[0]):
                    worst = ((b - a) / req_s[j], j, a, b)
        if worst is None:
            break
        _, j, a, b = worst
        lst = by_tgt[j]; mids = mids_by[j]
        k0 = bisect.bisect_left(mids, a + 120.0); k1 = bisect.bisect_right(mids, b - 120.0)
        centre = 0.5 * (a + b)
        order = sorted(range(k0, k1), key=lambda k: abs(mids[k] - centre))
        pick = best_pick(order[:40], lst, centre)
        if pick is not None and try_accept(pick):
            continue
        # bounded time-shift repair before rejecting this opportunity
        repaired = False
        for k in order[:10]:
            if try_accept(lst[k]):
                repaired = True; break
        if not repaired:
            break

    gaps = sim.max_gaps_hours(world, {j: [c.mid for c in chosen if c.tgt == j] for j in range(J)})
    req_true = np.array([t['expected_revisit_period_hours'] for t in targets], float)
    feasible = bool(np.all(gaps <= req_true + 1e-9)) and len(chosen) > 0
    # battery (approximate) on supplied ECI tracks, aligned with cand_by_sat order
    batt_ok = True
    if eci_by_sat is not None and sun_data is not None:
        acts_by = {}
        for s in range(len(cand_by_sat)):
            lst = sorted(per_sat[s], key=lambda c: c.start)
            arr = []
            prev = None
            for c in lst:
                sb = 0.0
                if prev is not None:
                    ang = math.degrees(math.acos(max(-1.0, min(1.0, float(np.dot(prev.los, c.los))))))
                    sb = sim.slew_time(ang, world) + settle
                arr.append((c.start, c.end, c.tgt, sb)); prev = c
            acts_by[s] = arr
        batt_ok = _battery_ok(world, eci_by_sat, acts_by, sun_data[0], sun_data[1])
    # independent final slew/settling/battery audit gates acceptance
    audit_ok = bool(batt_ok)
    for s in range(len(cand_by_sat)):
        lst = sorted(per_sat[s], key=lambda c: c.start)
        if not _pairwise_ok(lst):
            audit_ok = False; break
    actions = [(c.sat, c.tgt, float(c.start), float(c.end)) for c in chosen]
    return actions, gaps, feasible and audit_ok, audit_ok


def _score(world, n, gaps, ok):
    return float(sim.mission_score(world, n, gaps, bool(ok)))


# ---------------------------------------------------------------- solve
def solve(world, time_limit_s):
    t0 = time.time()
    limit = float(time_limit_s) if time_limit_s else 200.0
    soft = t0 + 0.70 * limit          # hard internal deadline near 70% of limit
    hard = soft
    # earlier phase sub-deadlines (fractions of the supplied limit) keep
    # total solve time bounded while the 70% hard deadline is the fallback
    family_deadline = min(hard, t0 + 0.20 * limit)
    growth_deadline = min(hard, t0 + 0.34 * limit)
    prune_deadline = min(hard, t0 + 0.42 * limit)
    targets = world['targets']; J = len(targets)
    cap = int(world['cap']); H = world['horizon_s']
    req_true = [float(t['expected_revisit_period_hours']) for t in targets]
    # requirement-exact internal target (<=0.02h epsilon safety margin)
    req_eff = [max(1.0, r - 0.02) for r in req_true]
    lats = np.array([abs(float(t['latitude_deg'])) for t in targets], float)
    lo_alt = float(world['model']['min_altitude_m']); hi_alt = float(world['model']['max_altitude_m'])
    alt_mid = _clip(700e3, lo_alt + 40000.0, hi_alt - 40000.0)
    alt_low = _clip(550e3, lo_alt + 40000.0, hi_alt - 40000.0)
    inc_lat = _clip(float(np.max(lats)) + 18.0 if J else 55.0, 50.0, 92.0)

    sun_data = None
    try:
        sun_data = _sun_hats(world)
    except Exception:
        sun_data = None

    cand_cache = {}    # element tuple -> (cand list with sat=0, ecef, eci subsample proxy)
    track_cache = {}

    def get_fast(el):
        """Cached fast track + candidates + ECI track for one element."""
        key = tuple(round(float(x), 6) for x in el)
        if key in cand_cache:
            return cand_cache[key]
        ecef = sim.fast_positions(world, [el])[0]
        # ECI from ECEF via inverse rotation, for battery simulation
        eci = np.einsum('tji,tj->ti', world['rot'], ecef)
        cands = _candidates_from_track(world, 0, ecef, margin_deg=1.2, buffer_steps=3,
                                       deadline=hard)
        cand_cache[key] = (cands, ecef, eci)
        return cand_cache[key]

    def evaluate_elements(els, deadline):
        """Schedule a constellation from cached fast candidates only
        (no exact propagation, no re-propagation in search loops)."""
        cand_by_sat = []; ecis = []
        for i, el in enumerate(els):
            if time.time() > deadline:
                break
            cs, _ec, eci = get_fast(el)
            # remap sat index to local position, preserving window bounds
            cand_by_sat.append([Cand(i, c.tgt, c.start, c.end, c.mid, c.los,
                                     c.win_start, c.win_end) for c in cs])
            ecis.append(eci)
        if len(cand_by_sat) != len(els):
            return None
        return _schedule(world, cand_by_sat, sun_data, ecis, req_eff, deadline)

    best = None  # (score, els, actions, gaps)

    def consider(els, result):
        nonlocal best
        if result is None:
            return
        actions, gaps, feasible, batt_ok = result
        if not actions:
            return
        sc = _score(world, len(els), gaps, batt_ok)
        # prefer feasible, then higher score, then fewer satellites
        key = (1 if feasible else 0, sc, -len(els))
        if best is None or key > best[0]:
            best = (key, list(els), list(actions), np.array(gaps), bool(feasible))

    # ---- Phase 1: guaranteed cap fallback (first config) + lean config screen
    configs = []
    for cfg in [(alt_mid, 55.0), (alt_mid, inc_lat), (alt_mid, 97.5), (alt_low, 55.0)]:
        if all(abs(cfg[0] - c[0]) > 1.0 or abs(cfg[1] - c[1]) > 0.5 for c in configs):
            configs.append(cfg)
    configs = configs[:4]

    cap_results = []
    for ci, (alt, inc) in enumerate(configs):
        # Lean: extra cap configs only if the floor is not yet feasible.
        if ci > 0 and (time.time() > soft or (best is not None and best[4])):
            break
        els = _walker_elements(cap, alt, inc)
        try:
            res = evaluate_elements(els, min(soft, time.time() + 0.25 * limit))
        except Exception:
            res = None
        consider(els, res)
        if res is not None:
            cap_results.append((alt, inc, els, res))
    # fallback must exist: if screening produced nothing, build baseline directly
    if best is None:
        els = _walker_elements(cap, alt_mid, 55.0)
        try:
            res = evaluate_elements(els, hard)
            consider(els, res)
        except Exception:
            pass
    if best is None:
        # Never-empty last resort: rebuild floor candidates via the sim
        # helper path (margin 0, no buffer) and schedule chronologically;
        # if that still yields nothing, emit the single earliest visible
        # window found by sim.visible. Never return empty actions.
        els = _walker_elements(cap, alt_mid, 55.0)
        states = [_state(el, world) for el in els]
        acts_fb = []
        try:
            cand_by_sat = []
            for i, el in enumerate(els):
                _cs, ecef_i, _eci = get_fast(el)
                cand_by_sat.append(_candidates_from_track(world, i, ecef_i, 0.0, 0))
            res_fb = _schedule(world, cand_by_sat, sun_data, None, req_true, hard)
            if res_fb is not None and res_fb[0]:
                acts_fb = list(res_fb[0])
        except Exception:
            acts_fb = []
        if not acts_fb:
            try:
                for i, el in enumerate(els):
                    if acts_fb:
                        break
                    ecef_i = sim.fast_positions(world, [el])[0]
                    vis_i = sim.visible(world, ecef_i)
                    for j, t in enumerate(world['targets']):
                        need = int(math.ceil(float(t['min_duration_sec']) / sim.STEP_S))
                        v = vis_i[j]
                        idx = np.where(v)[0]
                        for a in idx[::max(1, len(idx) // 50 or 1)]:
                            if a + need < len(v) and bool(np.all(v[a:a + need])):
                                s0 = float(world['times'][a])
                                acts_fb = [(i, j, s0, s0 + float(t['min_duration_sec']))]
                                break
                        if acts_fb:
                            break
            except Exception:
                pass
        return {'satellites': states, 'actions': acts_fb}

    # ---- Phase 1.5: geometry-diverse Walker families + constructive growth
    # Seed above is already stored as best-so-far before any of this work.
    grown_feasible = False
    try:
        if time.time() < family_deadline and best[4]:
            # base geometry derived only from world / best cap config
            if cap_results:
                _ba, _bi, _be, _br = max(
                    cap_results,
                    key=lambda it: _score(world, cap, it[3][1], it[3][3]) if it[3] else -1.0)
                base_alt, base_inc = float(_ba), float(_bi)
            else:
                base_alt, base_inc = alt_mid, 55.0
            p0 = max(2, int(round(math.sqrt(cap))))
            alt_hi = _clip(base_alt + 90000.0, lo_alt + 40000.0, hi_alt - 40000.0)
            alt_lo2 = _clip(base_alt - 90000.0, lo_alt + 40000.0, hi_alt - 40000.0)
            inc_alt = 97.5 if abs(base_inc - 97.5) > 10.0 else inc_lat
            # at most 4 families: vary plane distribution, phasing/RAAN
            # offset, one inclination offset and one altitude offset
            fam_specs = [
                (max(2, p0 - 1), 1, 0.0, base_alt, base_inc),
                (p0 + 2, 2, 180.0 / max(p0 + 2, 1), base_alt, _clip(base_inc + 6.0, 45.0, 98.0)),
                (p0, 3, 180.0 / max(p0, 1), alt_hi, inc_alt),
                (p0 + 1, 0, 90.0 / max(p0 + 1, 1), alt_lo2, inc_lat),
            ]
            n_red = int(min(cap, max(8, cap - 3)))
            fam_scored = []  # (violation, cap_elements)
            for (planes, phase, raan_off, falt, finc) in fam_specs:
                if time.time() > family_deadline:
                    break
                fam_els, _pids = _walker_family(cap, falt, finc, planes, phase, raan_off)
                # evenly-spaced reduced subset (subset of cap family, so
                # its cached candidates are reused by growth below)
                if n_red >= len(fam_els):
                    red_els = list(fam_els)
                else:
                    red_els = [fam_els[int(round(i * (len(fam_els) - 1) / max(n_red - 1, 1)))]
                               for i in range(n_red)]
                try:
                    rres = evaluate_elements(red_els, family_deadline)
                except Exception:
                    rres = None
                if rres is None:
                    continue
                viol = _gap_violation(rres[1], req_true)
                fam_scored.append((viol, fam_els))
                consider(red_els, rres)
            fam_scored.sort(key=lambda x: x[0])
            kept = fam_scored[:2]  # keep only best 1-2 families
            # candidate pool: union of kept cap families (deduplicated);
            # each element is fast-propagated at most once via get_fast cache
            pool = []
            seen_el = set()
            for _v, fam_els in kept:
                for el in fam_els:
                    k = tuple(round(float(x), 6) for x in el)
                    if k not in seen_el:
                        seen_el.add(k); pool.append(el)
            pool_cands = []
            for el in pool:
                if time.time() > growth_deadline:
                    break
                try:
                    cs, _ec, _ei = get_fast(el)
                except Exception:
                    cs = []
                pool_cands.append(cs)
            pool = pool[:len(pool_cands)]
            # bottom-up growth by verified marginal gap reduction
            cur_els = []; cur_res = None
            cur_viol = _gap_violation([H / 3600.0] * J, req_true)
            used = [False] * len(pool)
            while len(cur_els) < cap and time.time() < growth_deadline:
                # violated edge-inclusive intervals from current schedule
                mids_by_j = [[] for _ in range(J)]
                if cur_res is not None:
                    for (_s, _j, _a, _b) in cur_res[0]:
                        mids_by_j[int(_j)].append(0.5 * (_a + _b))
                bad_intervals = []  # (target, a_s, b_s)
                for j in range(J):
                    pts = [0.0] + sorted(mids_by_j[j]) + [H]
                    for a, b in zip(pts, pts[1:]):
                        if b - a > req_true[j] * 3600.0:
                            bad_intervals.append((j, a, b))
                if cur_res is not None and not bad_intervals:
                    break
                # cheap shortlist from cached candidates inside bad gaps
                short = []
                for pi, cs in enumerate(pool_cands):
                    if used[pi]:
                        continue
                    cov = 0.0
                    for c in cs:
                        for (j, a, b) in bad_intervals:
                            if c.tgt == j and a + 60.0 < c.mid < b - 60.0:
                                cov += 1.0 + (b - a) / max(req_true[j] * 3600.0, 1.0)
                                break
                    if cov > 0.0:
                        short.append((cov, pi))
                short.sort(reverse=True)
                trial_idxs = [pi for _cov, pi in short[:6]]
                if not trial_idxs:  # fall back to any unused satellite
                    trial_idxs = [pi for pi in range(len(pool)) if not used[pi]][:3]
                best_trial = None  # (violation, -feasible, pi, els, res)
                for pi in trial_idxs:
                    if time.time() > growth_deadline:
                        break
                    els_try = list(cur_els) + [pool[pi]]
                    try:
                        res_try = evaluate_elements(els_try, growth_deadline)
                    except Exception:
                        res_try = None
                    if res_try is None or not res_try[0]:
                        continue
                    v_try = _gap_violation(res_try[1], req_true)
                    key_t = (v_try, 0 if res_try[2] else 1)
                    if best_trial is None or key_t < best_trial[0]:
                        best_trial = (key_t, pi, els_try, res_try)
                if best_trial is None:
                    break
                _key_t, pi_best, cur_els, cur_res = best_trial
                used[pi_best] = True
                cur_viol = _key_t[0]
                consider(cur_els, cur_res)
                if cur_res[2]:
                    grown_feasible = True
                    break
                # no verified reduction and still infeasible: keep the
                # added satellite only if it was the best available; the
                # loop is bounded by cap and the growth deadline
    except Exception:
        grown_feasible = grown_feasible

    # ---- Phase 2: direct reduced Walkers for the best config(s)
    # rank configs by their cap result score
    def cfg_rank(item):
        _a, _i, _e, r = item
        return _score(world, cap, r[1], r[3]) if r else -1.0
    cap_results.sort(key=cfg_rank, reverse=True)
    tried_small = []
    if not grown_feasible and best[3] is not None and best[4]:
        for (alt, inc, _els, _r) in cap_results[:1]:
            if time.time() > prune_deadline:
                break
            n = cap - 3
            while n >= 5 and time.time() < prune_deadline:
                els = _walker_elements(n, alt, inc)
                try:
                    res = evaluate_elements(els, prune_deadline)
                except Exception:
                    res = None
                consider(els, res)
                tried_small.append((els, res))
                if res is not None and res[2]:
                    n -= 3
                else:
                    break

    # ---- Phase 3: verified pruning (singles, then pairs after singles stall)
    # A removal is accepted only when evaluate_elements (full cached
    # requirement-exact edge-inclusive re-schedule + final slew/battery
    # audit in _schedule) verifies every target; otherwise last verified
    # fleet in `best` is retained.
    if best[4] and time.time() < prune_deadline:
        stall_pairs_done = False
        while time.time() < prune_deadline and len(best[1]) > 4:
            cur_els = list(best[1]); cur_actions = list(best[2])
            counts = [0] * len(cur_els)
            for a in cur_actions:
                if 0 <= a[0] < len(counts):
                    counts[a[0]] += 1
            order = sorted(range(len(cur_els)), key=lambda i: counts[i])
            improved = False
            for idx in order:
                if time.time() > prune_deadline:
                    break
                els_try = [el for k, el in enumerate(cur_els) if k != idx]
                try:
                    res = evaluate_elements(els_try, prune_deadline)
                except Exception:
                    res = None
                if res is not None and res[2]:
                    consider(els_try, res); improved = True; break
            if improved:
                continue
            if stall_pairs_done:
                break
            stall_pairs_done = True
            # pairs only after singles stall
            pair_order = sorted(
                [(order[a], order[b]) for a in range(len(order))
                 for b in range(a + 1, len(order))],
                key=lambda p: counts[p[0]] + counts[p[1]])
            for (i1, i2) in pair_order:
                if time.time() > prune_deadline or len(best[1]) <= 5:
                    break
                els_try = [el for k, el in enumerate(cur_els) if k not in (i1, i2)]
                try:
                    res = evaluate_elements(els_try, prune_deadline)
                except Exception:
                    res = None
                if res is not None and res[2]:
                    consider(els_try, res); improved = True; break
            if not improved:
                break

    # ---- Phase 4: return best verified plan (no exact propagation)
    final_els, final_actions = list(best[1]), list(best[2])

    states = [_state(el, world) for el in final_els]
    # remap / validate action indices and sort
    acts = [(int(a[0]), int(a[1]), float(a[2]), float(a[3])) for a in final_actions
            if 0 <= int(a[0]) < len(states) and 0 <= int(a[1]) < J and 0.0 <= float(a[2]) < float(a[3]) <= H]
    acts.sort(key=lambda a: (a[0], a[2]))
    if not acts and best[2]:
        acts = [(int(a[0]), int(a[1]), float(a[2]), float(a[3])) for a in best[2]
                if 0 <= int(a[0]) < len(states) and 0 <= int(a[1]) < J]
        states = [_state(el, world) for el in best[1]]
        acts = [(int(a[0]), int(a[1]), float(a[2]), float(a[3])) for a in best[2]
                if 0 <= int(a[0]) < len(states) and 0 <= int(a[1]) < J and 0.0 <= float(a[2]) < float(a[3]) <= H]
    return {'satellites': states, 'actions': acts}
