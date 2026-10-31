"""Perturbed priced portfolio with dual averaging + unguarded exact polish.

Dual-averaged duplicate / per-satellite time-bin / battery-scarcity prices
over 8 priced rounds (decaying step, running averaged prices used for each
construction, feasible primal recovered and retained every round), plus a
fixed deterministic perturbation portfolio (duplicate/time-bin scales
0.85, 1.0, 1.15 and one scarcity-boosted variant). Every feasible primal
is retained; the per-mission winner is selected by the exact whole-plan
score (ties: higher WCR, then lower TAT, then lexicographically smallest
sorted task set) and all remaining time goes to winner-only polish that
accepts only strictly positive exact whole-plan deltas. The latency price
is kept at the cycle-7 setting: no latency term is added in priced
construction or DP utility. Battery feasibility is checked incrementally
in every construction/restart/polish insertion and the final plan is
validated with sim.check with a deterministic fallback.

Battery-aware regret greedy + multi-sat segment DP + heavy ejection chains.

Cycle-4: jointly re-optimises contiguous high unscheduled-weight-density
segments across 2-3 satellites (segment cleared, rebuilt by sequential
per-satellite DP offering rejected candidates to the next pooled satellite,
pool mixing cleared incumbents and unscheduled candidates) and runs
depth-up-to-3 heavy-first ejection chains displacing lowest
weight-per-occupied-time incumbents with cross-satellite reinsertion of
displaced tasks. Segment rebuilds and ejection chains are accepted only
when the exact whole-plan objective delta (fast_N: WCR/CR/TAT/PC) is
strictly positive and sim.check validates the plan.

Per-satellite weighted interval-scheduling DP (slew-feasible transitions,
exact-marginal-gain node values ranked by gain per occupied slew-plus-
duration time) re-chains a widened pool -- selected, blocking/overlapping
unscheduled, top per-task alternatives and highest-weight unscheduled
opportunities -- ejecting lower-density blockers. Depth-2 cross-satellite
ejection reinserts ejected tasks on any satellite. A move is accepted only
when the exact internal score improves and sim.check (full battery
simulation) validates it. This alternates with deterministic
destroy-and-repair LNS, with most of the budget spent on DP/ejection.

Constructive phase: regret-based weighted insertion. Each opportunity is
scored by its marginal objective gain (weighted completion + completion
count + release-to-completion latency + energy cost) per unit consumed
time (duration + slew), plus a regret bonus equal to the gap between the
task's best and second-best opportunity scores (tasks whose best chance
is scarce are inserted before that chance is consumed).
Improvement phase: time-budgeted large-neighbourhood search (random /
worst-contribution / time-window destroy + regret reinsertion, plus
1-for-1 and 1-for-2 swaps) accepting only feasible states whose true
WCR/CR/TAT/PC objective improves.
Battery feasibility is checked incrementally during every insertion
(conservative idle-trajectory slack guard) and the final selection is
validated with sim.check, with a deterministic drop-lowest-contribution
fallback (then a baseline-subset fallback) so an invalid plan is never
returned. All randomness uses a fixed seed; everything is derived from
the world argument.
"""
import bisect
import random
import time

import numpy as np
import sim


def solve(world, time_limit_s):
    t0 = time.time()
    try:
        budget = float(time_limit_s) if time_limit_s else 60.0
    except Exception:
        budget = 60.0
    # Self-imposed stop at 90% of the limit; main search ends earlier so the
    # final sim.check validation/fallback always has reserve time.
    hard_deadline = t0 + max(5.0, min(budget - 2.0, budget * 0.90))
    lns_deadline = t0 + max(4.0, budget * 0.82)
    construct_deadline = t0 + max(3.0, budget * 0.15)
    rng = random.Random(20261030)

    sat_a = world['sat']
    task_a = world['task']
    start_a = world['start_s']
    end_a = world['end_s']
    nadir_a = world['nadir_slew_s']
    n = int(len(sat_a))
    satellites = world['satellites']
    tasks = world['tasks']
    n_sat = len(satellites)
    n_tasks = len(tasks)
    H = float(world['horizon_s'])
    E_budget = float(world['energy_budget_wh']) if float(world['energy_budget_wh']) > 0 else 1.0

    sat_l = [int(x) for x in sat_a]
    task_l = [int(x) for x in task_a]
    start_l = [float(x) for x in start_a]
    end_l = [float(x) for x in end_a]
    nadir_l = [float(x) for x in nadir_a]
    dur_l = [end_l[k] - start_l[k] for k in range(n)]
    task_weight = [float(t['weight']) for t in tasks]
    task_release = [float(t['release_s']) for t in tasks]
    W_total = sum(task_weight) if sum(task_weight) > 0 else 1.0

    # ---- battery idle trajectories and suffix-min slack per satellite ----
    step = int(world['sunlit_step_s']) if int(world['sunlit_step_s']) > 0 else 60
    sunlit = world['sunlit']
    suffix_min = []  # per sat: suffix minimum of idle-only battery level
    pc_idle = 0.0
    for si, S in enumerate(satellites):
        pc_idle += float(S['idle_power_w']) * H / 3600.0
        n_steps = int(sunlit.shape[1]) if hasattr(sunlit, 'shape') else 0
        if n_steps <= 0:
            suffix_min.append([float(S['initial_battery_wh'])])
            continue
        bat = float(S['initial_battery_wh'])
        cap = float(S['battery_capacity_wh'])
        idle = float(S['idle_power_w'])
        charge = float(S['sunlit_charge_power_w'])
        levels = [0.0] * (n_steps + 1)
        levels[0] = bat
        row = sunlit[si]
        for i in range(n_steps):
            delta = ((charge if bool(row[i]) else 0.0) - idle) * step / 3600.0
            bat += delta
            if bat > cap:
                bat = cap
            levels[i + 1] = bat
        suf = [0.0] * (n_steps + 2)
        cur = float('inf')
        for i in range(n_steps, -1, -1):
            if levels[i] < cur:
                cur = levels[i]
            suf[i] = cur
        suf[n_steps + 1] = cur
        suffix_min.append(suf)

    gap_cache = {}

    def gap(i, j):
        key = (i, j)
        v = gap_cache.get(key)
        if v is None:
            v = float(sim.required_gap_s(world, i, j))
            gap_cache[key] = v
        return v

    # ---- opportunity priority: marginal gain per unit time + regret ----
    base_val = [0.0] * n
    for k in range(n):
        t = task_l[k]
        lat_frac = 1.0 - max(0.0, end_l[k] - task_release[t]) / H
        if lat_frac < 0.0:
            lat_frac = 0.0
        # marginal objective (fraction): 0.45*dWCR + 0.20*dCR + latency/energy tie terms
        gain = 0.45 * task_weight[t] / W_total + 0.20 / max(1, n_tasks) \
            + 0.02 * lat_frac / max(1, n_tasks)
        base_val[k] = gain / max(1.0, dur_l[k] + 12.0)

    opps_by_task = [[] for _ in range(n_tasks)]
    for k in range(n):
        opps_by_task[task_l[k]].append(k)
    regret = [0.0] * n_tasks
    task_best_prio = [0.0] * n_tasks
    for t in range(n_tasks):
        lst = opps_by_task[t]
        lst.sort(key=lambda kk: (-base_val[kk], start_l[kk], kk))
        if lst:
            task_best_prio[t] = base_val[lst[0]]
            if len(lst) >= 2:
                regret[t] = max(0.0, base_val[lst[0]] - base_val[lst[1]])
            else:
                regret[t] = base_val[lst[0]]  # single chance: maximal regret
    prio = [base_val[k] + regret[task_l[k]] for k in range(n)]
    # re-sort per-task lists by full priority for repair attempts
    for t in range(n_tasks):
        opps_by_task[t].sort(key=lambda kk: (-prio[kk], start_l[kk], kk))
        if opps_by_task[t]:
            task_best_prio[t] = prio[opps_by_task[t][0]]

    # per-satellite opportunities sorted by descending priority (chain-DP pool)
    opps_by_sat_prio = [[] for _ in range(n_sat)]
    for k in range(n):
        opps_by_sat_prio[sat_l[k]].append(k)
    for si in range(n_sat):
        opps_by_sat_prio[si].sort(key=lambda kk: (-prio[kk], start_l[kk], kk))

    def opp_value(k):
        # Exact marginal objective gain (in N points, up to the shared
        # latency-denominator / energy terms) of completing task of k.
        t = task_l[k]
        lat = 1.0 - max(0.0, end_l[k] - task_release[t]) / H
        if lat < 0.0:
            lat = 0.0
        return (45.0 * task_weight[t] / W_total + 20.0 / max(1, n_tasks)
                + 2.0 * lat / max(1, n_tasks))

    # Exact-objective gain, occupied time (duration + slew proxy) and density.
    val_l = [opp_value(k) for k in range(n)]
    occ_l = [dur_l[k] + max(5.0, min(90.0, nadir_l[k])) for k in range(n)]
    dens_l = [val_l[k] / max(1.0, occ_l[k]) for k in range(n)]
    lat_l = [max(0.0, 1.0 - max(0.0, end_l[k] - task_release[task_l[k]]) / H)
             for k in range(n)]
    tasks_by_weight = sorted(range(n_tasks), key=lambda t: (-task_weight[t], t))
    # Per-satellite opportunities in start-time order (blocking-opportunity pool).
    opps_by_sat_time = [[] for _ in range(n_sat)]
    for k in range(n):
        opps_by_sat_time[sat_l[k]].append(k)
    sat_time_starts = []
    for si in range(n_sat):
        opps_by_sat_time[si].sort(key=lambda kk: (start_l[kk], end_l[kk], kk))
        sat_time_starts.append([start_l[kk] for kk in opps_by_sat_time[si]])

    # ---- Lagrangian pricing state (prices in prio / per-time units) ----
    # Contention statistics computed from world only: per-task opportunity
    # counts (opps_by_task), per-satellite 600s time-bin candidate load,
    # and a battery-scarcity indicator from idle-trajectory slack.
    BIN_W = 600.0
    n_bins = max(1, int(H // BIN_W) + 1)
    bin_idx_l = [min(n_bins - 1, max(0, int(start_l[k] // BIN_W))) for k in range(n)]
    sat_bin_load = [[0] * n_bins for _ in range(n_sat)]
    for k in range(n):
        sat_bin_load[sat_l[k]][bin_idx_l[k]] += 1
    prio_scale = float(np.median(np.array(prio))) if n else 1e-12
    if not (prio_scale > 0):
        prio_scale = 1e-12
    PRICE_DUP = [0.0] * n_tasks
    PRICE_BIN = [[0.0] * n_bins for _ in range(n_sat)]
    PRICE_BATT = [0.0] * n_sat
    for si in range(n_sat):
        cap_wh = float(satellites[si]['battery_capacity_wh']) or 1.0
        min_idle = suffix_min[si][0] if suffix_min[si] else cap_wh
        scarcity = min(1.0, max(0.0, 1.0 - min_idle / cap_wh))
        PRICE_BATT[si] = 0.15 * prio_scale * scarcity

    def dp_node_value(k, mode):
        # Priced DP node value: final Lagrangian prices enter as additive
        # node costs (duplicate + time-bin congestion + battery scarcity),
        # converted from per-time prio units to objective-value units.
        pen = PRICE_DUP[task_l[k]] + PRICE_BIN[sat_l[k]][bin_idx_l[k]] + PRICE_BATT[sat_l[k]]
        pv = val_l[k] - pen * max(1.0, occ_l[k]) * 100.0
        if pv < 0.05 * val_l[k]:
            pv = 0.05 * val_l[k]
        if mode == 1:
            return pv * (60.0 / (60.0 + occ_l[k])) ** 0.5
        if mode == 2:
            return pv * (0.60 + 0.80 * lat_l[k])
        return pv

    # ---- state handling ----
    def new_state():
        return {
            'chains': [[] for _ in range(n_sat)],
            'starts': [[] for _ in range(n_sat)],
            'cums': [[] for _ in range(n_sat)],  # cumulative extra Wh incl. this obs
            'totals': [0.0] * n_sat,
            'done': set(),
            'chosen': set(),
        }

    def copy_state(st):
        return {
            'chains': [c[:] for c in st['chains']],
            'starts': [c[:] for c in st['starts']],
            'cums': [c[:] for c in st['cums']],
            'totals': st['totals'][:],
            'done': set(st['done']),
            'chosen': set(st['chosen']),
        }

    def extra_of(k, slew_before_s, si):
        S = satellites[si]
        return (float(S['imaging_power_w']) * dur_l[k]
                + float(S['slew_power_w']) * max(0.0, slew_before_s)) / 3600.0

    def battery_ok(si, start_k, new_total):
        suf = suffix_min[si]
        idx = int(start_k // step)
        if idx < 0:
            idx = 0
        if idx >= len(suf):
            idx = len(suf) - 1
        return suf[idx] - new_total >= -1e-9

    def try_insert(st, k):
        """Incremental feasibility: overlap, slew gaps, battery. Insert if ok."""
        si = sat_l[k]
        t = task_l[k]
        if t in st['done'] or k in st['chosen']:
            return False
        chain = st['chains'][si]
        starts = st['starts'][si]
        pos = bisect.bisect_left(starts, start_l[k])
        pred = chain[pos - 1] if pos > 0 else None
        succ = chain[pos] if pos < len(chain) else None
        if pred is not None and end_l[pred] > start_l[k] + 1e-9:
            return False
        if succ is not None and end_l[k] > start_l[succ] + 1e-9:
            return False
        if pred is None:
            slew_before = nadir_l[k]
            if start_l[k] + 1e-9 < nadir_l[k]:
                return False
        else:
            g = gap(pred, k)
            if start_l[k] - end_l[pred] + 1e-9 < g:
                return False
            slew_before = g
        delta_succ = 0.0
        if succ is not None:
            g2 = gap(k, succ)
            if start_l[succ] - end_l[k] + 1e-9 < g2:
                return False
            old_slew = nadir_l[succ] if pred is None else gap(pred, succ)
            delta_succ = (float(satellites[si]['slew_power_w'])
                          * (g2 - old_slew)) / 3600.0
        extra_k = extra_of(k, slew_before, si)
        add = extra_k + delta_succ
        new_total = st['totals'][si] + add
        if not battery_ok(si, start_l[k], new_total):
            return False
        # commit
        chain.insert(pos, k)
        starts.insert(pos, start_l[k])
        cums = st['cums'][si]
        cum_before = cums[pos - 1] if pos > 0 else 0.0
        cums.insert(pos, cum_before + extra_k)
        for i in range(pos + 1, len(cums)):
            cums[i] += add
        st['totals'][si] = new_total
        st['done'].add(t)
        st['chosen'].add(k)
        return True

    def remove_opp(st, k):
        si = sat_l[k]
        chain = st['chains'][si]
        starts = st['starts'][si]
        pos = bisect.bisect_left(starts, start_l[k])
        while pos < len(chain) and chain[pos] != k:
            pos += 1
        if pos >= len(chain):
            return False
        pred = chain[pos - 1] if pos > 0 else None
        succ = chain[pos + 1] if pos + 1 < len(chain) else None
        slew_before = nadir_l[k] if pred is None else gap(pred, k)
        extra_k = extra_of(k, slew_before, si)
        delta_succ = 0.0
        if succ is not None:
            old_slew = gap(k, succ)
            new_slew = nadir_l[succ] if pred is None else gap(pred, succ)
            delta_succ = (float(satellites[si]['slew_power_w'])
                          * (new_slew - old_slew)) / 3600.0
        change = -extra_k + delta_succ
        cums = st['cums'][si]
        del chain[pos]
        del starts[pos]
        del cums[pos]
        for i in range(pos, len(cums)):
            cums[i] += change
        st['totals'][si] += change
        st['done'].discard(task_l[k])
        st['chosen'].discard(k)
        return True

    def fast_N(st):
        """True WCR/CR/TAT/PC objective (mirrors sim.check scoring)."""
        if not st['chosen']:
            return -1.0
        w_done = 0.0
        tat_sum = 0.0
        cnt = 0
        for k in st['chosen']:
            t = task_l[k]
            w_done += task_weight[t]
            tat_sum += end_l[k] - task_release[t]
            cnt += 1
        if cnt == 0:
            return -1.0
        wcr = w_done / W_total
        cr = cnt / max(1, n_tasks)
        tat = tat_sum / cnt
        pc = pc_idle + sum(st['totals'])
        cl = lambda x: min(1.0, max(0.0, x))
        return 100.0 * (0.45 * wcr + 0.20 * cr + 0.20 * cl(1.0 - tat / H)
                        + 0.15 * cl(1.0 - pc / E_budget))

    def marginal_density(st, k):
        si = sat_l[k]
        chain = st['chains'][si]
        starts = st['starts'][si]
        pos = bisect.bisect_left(starts, start_l[k])
        slew = nadir_l[k]
        if pos < len(chain) and chain[pos] == k and pos > 0:
            slew = gap(chain[pos - 1], k)
        elif pos > 0 and pos - 1 < len(chain):
            # k may not be located exactly; fall back to nadir estimate
            slew = nadir_l[k]
        return base_val[k] * max(1.0, dur_l[k] + 12.0) / max(1.0, dur_l[k] + slew)

    # ---- Dual-averaged priced construction + perturbation portfolio ----
    # 8 rounds: running averaged prices price each construction, a feasible
    # primal is recovered and retained every round, then a clamped
    # subgradient step with decaying step size updates the raw prices and
    # the running average. No latency term is used in the priced order.
    priced_deadline = t0 + max(3.0, budget * 0.26)
    perturb_deadline = t0 + max(4.0, budget * 0.34)
    if priced_deadline > hard_deadline:
        priced_deadline = hard_deadline
    if perturb_deadline > hard_deadline:
        perturb_deadline = hard_deadline

    def construct_priced(deadline):
        st = new_state()
        dup_skip = [0] * n_tasks
        bin_fail = [[0] * n_bins for _ in range(n_sat)]
        order = sorted(range(n), key=lambda kk: (
            -(prio[kk] - PRICE_DUP[task_l[kk]]
              - PRICE_BIN[sat_l[kk]][bin_idx_l[kk]] - PRICE_BATT[sat_l[kk]]),
            start_l[kk], kk))
        for idx, k in enumerate(order):
            if task_l[k] in st['done']:
                dup_skip[task_l[k]] += 1
                continue
            if (idx & 1023) == 0 and time.time() > deadline:
                break
            if not try_insert(st, k):
                bin_fail[sat_l[k]][bin_idx_l[k]] += 1
        return st, dup_skip, bin_fail

    def exact_key(st):
        # Exact whole-plan score with deterministic tie-breaking.
        if not st['chosen']:
            return (-1.0, 0.0, 0.0, [])
        w_done = 0.0
        tat_sum = 0.0
        cnt = 0
        for k in st['chosen']:
            t = task_l[k]
            w_done += task_weight[t]
            tat_sum += end_l[k] - task_release[t]
            cnt += 1
        wcr = w_done / W_total
        tat = tat_sum / max(1, cnt)
        return (fast_N(st), wcr, tat, sorted(st['done']))

    def better_exact(a_key, b_key):
        if a_key[0] != b_key[0]:
            return a_key[0] > b_key[0]
        if a_key[1] != b_key[1]:
            return a_key[1] > b_key[1]
        if a_key[2] != b_key[2]:
            return a_key[2] < b_key[2]
        return a_key[3] < b_key[3]

    retained_primals = []  # list of (variant_label, state, exact_key)
    _winning_variant_label = None

    def retain(label, st):
        if st is not None and st['chosen']:
            retained_primals.append((label, st, exact_key(st)))

    AVG_DUP = PRICE_DUP[:]
    AVG_BIN = [row[:] for row in PRICE_BIN]
    AVG_BATT = PRICE_BATT[:]
    DUAL_AVERAGING_ROUNDS = 8
    for _round in range(DUAL_AVERAGING_ROUNDS):
        if time.time() > priced_deadline and retained_primals:
            break
        # Price this round with the running averaged prices.
        for t in range(n_tasks):
            PRICE_DUP[t] = AVG_DUP[t]
        for si in range(n_sat):
            PRICE_BATT[si] = AVG_BATT[si]
            for b in range(n_bins):
                PRICE_BIN[si][b] = AVG_BIN[si][b]
        st_r, dup_skip, bin_fail = construct_priced(priced_deadline)
        retain('dual_avg_round_%d' % _round, st_r)
        # Raw subgradient step, deterministically decaying with round.
        step_decay = 1.0 / (1.0 + 0.35 * _round)
        cap_price = 2.0 * prio_scale
        raw_dup = PRICE_DUP[:]
        raw_batt = PRICE_BATT[:]
        raw_bin = [row[:] for row in PRICE_BIN]
        for t in range(n_tasks):
            excess = dup_skip[t] - 1
            if excess > 0:
                raw_dup[t] = min(cap_price, AVG_DUP[t] + step_decay * 0.05 * prio_scale * min(3, excess))
            elif AVG_DUP[t] > 0.0:
                raw_dup[t] = max(0.0, AVG_DUP[t] - step_decay * 0.01 * prio_scale)
        for si in range(n_sat):
            headroom = suffix_min[si][0] if suffix_min[si] else 1.0
            util = st_r['totals'][si] / max(1.0, headroom)
            if util > 0.05:
                raw_batt[si] = min(cap_price, AVG_BATT[si] + step_decay * 0.04 * prio_scale)
            bf = bin_fail[si]
            load = sat_bin_load[si]
            for b in range(n_bins):
                if bf[b] > 0 and load[b] > 0:
                    raw_bin[si][b] = min(cap_price, AVG_BIN[si][b] + step_decay * 0.03 * prio_scale * min(4, bf[b]))
                elif AVG_BIN[si][b] > 0.0:
                    raw_bin[si][b] = max(0.0, AVG_BIN[si][b] - step_decay * 0.005 * prio_scale)
        # Dual averaging: running average of raw iterates.
        w_new = 1.0 / (_round + 1)
        for t in range(n_tasks):
            AVG_DUP[t] = AVG_DUP[t] * (1.0 - w_new) + raw_dup[t] * w_new
        for si in range(n_sat):
            AVG_BATT[si] = AVG_BATT[si] * (1.0 - w_new) + raw_batt[si] * w_new
            for b in range(n_bins):
                AVG_BIN[si][b] = AVG_BIN[si][b] * (1.0 - w_new) + raw_bin[si][b] * w_new
    # Restore averaged prices for DP utility and perturbed restarts.
    for t in range(n_tasks):
        PRICE_DUP[t] = AVG_DUP[t]
    for si in range(n_sat):
        PRICE_BATT[si] = AVG_BATT[si]
        for b in range(n_bins):
            PRICE_BIN[si][b] = AVG_BIN[si][b]
    base_dup = PRICE_DUP[:]
    base_bin = [row[:] for row in PRICE_BIN]
    base_batt = PRICE_BATT[:]
    # Unperturbed cycle-7-style construction at averaged prices (scale 1.0
    # is also in the portfolio below; this retains the plain primal too).
    if time.time() <= perturb_deadline:
        st_u, _ds, _bf = construct_priced(perturb_deadline)
        retain('unperturbed', st_u)
    # Fixed deterministic perturbation portfolio, in fixed order.
    PERTURB_SCALES = [0.85, 1.0, 1.15]
    for _pi, _scale in enumerate(PERTURB_SCALES):
        if time.time() > perturb_deadline and retained_primals:
            break
        for t in range(n_tasks):
            PRICE_DUP[t] = base_dup[t] * _scale
        for si in range(n_sat):
            PRICE_BATT[si] = base_batt[si] * _scale
            for b in range(n_bins):
                PRICE_BIN[si][b] = base_bin[si][b] * _scale
        st_p, _ds, _bf = construct_priced(perturb_deadline)
        retain('perturb_scale_%.2f' % _scale, st_p)
    # Scarcity-boosted variant: battery prices boosted where idle slack is low.
    if time.time() <= perturb_deadline or not retained_primals:
        for t in range(n_tasks):
            PRICE_DUP[t] = base_dup[t]
        for si in range(n_sat):
            cap_wh = float(satellites[si]['battery_capacity_wh']) or 1.0
            min_idle = suffix_min[si][0] if suffix_min[si] else cap_wh
            scarcity = min(1.0, max(0.0, 1.0 - min_idle / cap_wh))
            PRICE_BATT[si] = min(2.0 * prio_scale, base_batt[si] * 1.15 + 0.25 * prio_scale * scarcity)
            for b in range(n_bins):
                PRICE_BIN[si][b] = base_bin[si][b]
        st_p, _ds, _bf = construct_priced(perturb_deadline)
        retain('perturb_scarcity_boost', st_p)
    # Restore averaged (unperturbed) prices so segment-DP uses them.
    for t in range(n_tasks):
        PRICE_DUP[t] = base_dup[t]
    for si in range(n_sat):
        PRICE_BATT[si] = base_batt[si]
        for b in range(n_bins):
            PRICE_BIN[si][b] = base_bin[si][b]
    # Select winner from all retained primals by exact whole-plan score.
    state = None
    if retained_primals:
        _best_i = 0
        for _i in range(1, len(retained_primals)):
            if better_exact(retained_primals[_i][2], retained_primals[_best_i][2]):
                _best_i = _i
        _winning_variant_label = retained_primals[_best_i][0]
        state = retained_primals[_best_i][1]
    else:
        state = new_state()
        order = sorted(range(n), key=lambda kk: (-prio[kk], start_l[kk], kk))
        for idx, k in enumerate(order):
            if task_l[k] in state['done']:
                continue
            if (idx & 1023) == 0 and time.time() > construct_deadline:
                break
            try_insert(state, k)

    best_state = copy_state(state)
    best_score = fast_N(state)
    cur_state = state
    cur_score = best_score

    # tasks ordered by best priority for repair pools
    tasks_by_prio = sorted(range(n_tasks), key=lambda t: (-task_best_prio[t], t))

    def repair(st, pool_tasks, deadline, max_opps=6):
        for t in pool_tasks:
            if t in st['done']:
                continue
            for k in opps_by_task[t][:max_opps]:
                if try_insert(st, k):
                    break
            if (len(st['chosen']) & 255) == 0 and time.time() > deadline:
                break

    # ---- per-satellite chain-DP ejection repair ----
    def chain_dp_for_sat(st, si, max_pool=430, mode=0):
        """Widened weighted interval-scheduling DP for satellite si.

        Pool = selected opportunities + unscheduled opportunities that
        overlap / slew-block a selected one + the best opportunity per
        unscheduled task on this satellite + opportunities of the
        highest-weight unscheduled tasks (one per task, so a DP chain can
        never count a task twice). Pool pruning and tie-breaking rank by
        dens_l = exact-objective gain per occupied (slew+duration) time.
        Edge p->k allowed only if the exact sim.required_gap_s slew gap
        fits; first node must satisfy nadir. Returns the DP chain."""
        scheduled = list(st['chains'][si])
        cand = list(scheduled)
        in_pool = set(scheduled)
        pool_tasks = set(task_l[k] for k in scheduled)

        def add_opp(k):
            t = task_l[k]
            if k in in_pool or t in pool_tasks or t in st['done']:
                return False
            in_pool.add(k)
            pool_tasks.add(t)
            cand.append(k)
            return True

        # Best opportunity per unscheduled task on this satellite, per mode.
        best_per_task = {}
        for k in opps_by_sat_prio[si]:
            t = task_l[k]
            if t in st['done'] or t in pool_tasks:
                continue
            cur = best_per_task.get(t)
            key = (dp_node_value(k, mode) / max(1.0, occ_l[k]), -start_l[k], -k)
            if cur is None or key > cur[0]:
                best_per_task[t] = (key, k)
        # (a) Blocking/overlapping unscheduled: time-near any selected opp.
        blocking = []
        time_opps = opps_by_sat_time[si]
        time_starts = sat_time_starts[si]
        for sk in scheduled:
            lo = bisect.bisect_left(time_starts, start_l[sk] - 2700.0)
            hi = bisect.bisect_right(time_starts, end_l[sk] + 2700.0)
            for idx in range(lo, hi):
                k = time_opps[idx]
                t = task_l[k]
                if k in in_pool or t in pool_tasks or t in st['done']:
                    continue
                if end_l[k] > start_l[sk] - 2700.0 and start_l[k] < end_l[sk] + 2700.0:
                    blocking.append(k)
        blocking.sort(key=lambda kk: (-dens_l[kk], start_l[kk], kk))
        for k in blocking[:170]:
            add_opp(k)
        # (b) Highest-weight unscheduled tasks with an opportunity here.
        added_w = 0
        for t in tasks_by_weight:
            if added_w >= 110 or len(cand) >= max_pool:
                break
            if t in st['done'] or t in pool_tasks:
                continue
            ent = best_per_task.get(t)
            if ent is not None and add_opp(ent[1]):
                added_w += 1
        # (c) Top per-task alternatives ranked by gain per occupied time.
        rest = sorted(best_per_task.values(),
                      key=lambda e: (-dens_l[e[1]], start_l[e[1]], e[1]))
        for _key, k in rest:
            if len(cand) >= max_pool:
                break
            add_opp(k)
        if not cand:
            return scheduled
        cand.sort(key=lambda kk: (end_l[kk], start_l[kk], kk))
        m = len(cand)
        vals = [dp_node_value(k, mode) for k in cand]
        neg = -1e18
        dp = [neg] * m
        prev = [-1] * m
        for j in range(m):
            kj = cand[j]
            best = neg
            best_p = -1
            if start_l[kj] + 1e-9 >= nadir_l[kj]:
                best = 0.0
            checked = 0
            for p in range(j - 1, -1, -1):
                if dp[p] == neg:
                    continue
                kp = cand[p]
                if task_l[kp] == task_l[kj]:
                    continue
                if end_l[kp] > start_l[kj] + 1e-9:
                    continue
                checked += 1
                if checked > 44:
                    break
                if start_l[kj] - end_l[kp] + 1e-9 < gap(kp, kj):
                    continue
                if dp[p] > best:
                    best = dp[p]
                    best_p = p
            if best != neg:
                dp[j] = best + vals[j]
                prev[j] = best_p
        best_j = -1
        best_v = neg
        for j in range(m):
            if dp[j] > best_v:
                best_v = dp[j]
                best_j = j
        if best_j < 0:
            return scheduled
        chain = []
        j = best_j
        while j >= 0:
            chain.append(cand[j])
            j = prev[j]
        chain.reverse()
        chain.sort(key=lambda kk: (start_l[kk], kk))
        return chain

    def apply_chain_dp(st, si, deadline, mode=0):
        """Build candidate by DP chain on si, eject blockers, cross-sat repair.
        Returns (candidate_state, candidate_score) or (None, -1)."""
        if time.time() > deadline:
            return None, -1.0
        old_chain = list(st['chains'][si])
        new_chain = chain_dp_for_sat(st, si, mode=mode)
        if set(new_chain) == set(old_chain):
            return None, -1.0
        cand = copy_state(st)
        ejected_tasks = [task_l[k] for k in old_chain if k not in set(new_chain)]
        for k in old_chain:
            remove_opp(cand, k)
        for k in new_chain:
            try_insert(cand, k)
        # ejection repair: ejected tasks first on any compatible satellite
        for t in ejected_tasks:
            if t in cand['done']:
                continue
            for k in opps_by_task[t][:6]:
                if try_insert(cand, k):
                    break
        # bounded general repair with rotating high-priority undone tasks
        extra = []
        for t in tasks_by_prio:
            if t not in cand['done']:
                extra.append(t)
            if len(extra) >= 80:
                break
        repair(cand, extra, deadline, max_opps=4)
        sc = fast_N(cand)
        return cand, sc

    def cross_sat_ejection(st, deadline, task_cursor, max_attempts=46):
        """Depth-2 cross-satellite ejection for high-value unscheduled tasks.

        For each candidate opportunity, identify its (at most 2) immediate
        slew/overlap blockers on that satellite; skip unless the candidate's
        exact gain or density beats the blockers'. Eject the blockers,
        insert the candidate (incremental slew + battery guard via
        try_insert), then try to reinsert every ejected task on any
        satellite/gap. Keep a move only on exact-score gain + sim.check."""
        cur = st
        cur_sc = fast_N(cur)
        attempts = 0
        order = tasks_by_weight[task_cursor:] + tasks_by_weight[:task_cursor]
        next_cursor = task_cursor
        for t in order:
            if attempts >= max_attempts or time.time() > deadline:
                break
            next_cursor = (next_cursor + 1) % max(1, n_tasks)
            if t in cur['done']:
                continue
            for k in opps_by_task[t][:8]:
                if attempts >= max_attempts or time.time() > deadline:
                    break
                si = sat_l[k]
                chain = cur['chains'][si]
                starts = cur['starts'][si]
                if not chain:
                    continue
                pos = bisect.bisect_left(starts, start_l[k])
                blockers = []
                pred = chain[pos - 1] if pos > 0 else None
                succ = chain[pos] if pos < len(chain) else None
                if pred is not None and (end_l[pred] > start_l[k] + 1e-9
                        or start_l[k] - end_l[pred] + 1e-9 < gap(pred, k)):
                    blockers.append(pred)
                if succ is not None and (end_l[k] > start_l[succ] + 1e-9
                        or start_l[succ] - end_l[k] + 1e-9 < gap(k, succ)):
                    blockers.append(succ)
                if not blockers or len(blockers) > 2:
                    continue
                b_val = sum(val_l[b] for b in blockers)
                b_dens = max(dens_l[b] for b in blockers)
                if val_l[k] < 0.90 * b_val and dens_l[k] < b_dens:
                    continue
                attempts += 1
                cand = copy_state(cur)
                ejected = [task_l[b] for b in blockers]
                for b in blockers:
                    remove_opp(cand, b)
                if not try_insert(cand, k):
                    continue
                for et in ejected:
                    if et in cand['done']:
                        continue
                    for ek in opps_by_task[et][:6]:
                        if try_insert(cand, ek):
                            break
                sc = fast_N(cand)
                if sc > cur_sc + 1e-9 and full_valid(sorted(cand['chosen'])):
                    cur = cand
                    cur_sc = sc
                    break
        return cur, cur_sc, next_cursor

    def full_valid(selection):
        try:
            rep = sim.check(world, list(selection))
            return bool(rep.get('valid'))
        except Exception:
            return False

    def _dp_chain_from_pool(pool, mode):
        # Weighted interval DP on a one-per-task pool; slew via cached gap().
        if not pool:
            return []
        cand = sorted(set(pool), key=lambda kk: (end_l[kk], start_l[kk], kk))
        m = len(cand)
        vals = [dp_node_value(k, mode) for k in cand]
        neg = -1e18
        dp = [neg] * m
        prev = [-1] * m
        for j in range(m):
            kj = cand[j]
            best = neg
            best_p = -1
            if start_l[kj] + 1e-9 >= nadir_l[kj]:
                best = 0.0
            checked = 0
            for p in range(j - 1, -1, -1):
                if dp[p] == neg:
                    continue
                kp = cand[p]
                if task_l[kp] == task_l[kj] or end_l[kp] > start_l[kj] + 1e-9:
                    continue
                checked += 1
                if checked > 40:
                    break
                if start_l[kj] - end_l[kp] + 1e-9 < gap(kp, kj):
                    continue
                if dp[p] > best:
                    best = dp[p]
                    best_p = p
            if best != neg:
                dp[j] = best + vals[j]
                prev[j] = best_p
        best_j = -1
        best_v = neg
        for j in range(m):
            if dp[j] > best_v:
                best_v = dp[j]
                best_j = j
        if best_j < 0:
            return []
        chain = []
        j = best_j
        while j >= 0:
            chain.append(cand[j])
            j = prev[j]
        chain.reverse()
        chain.sort(key=lambda kk: (start_l[kk], kk))
        return chain

    def segment_dp_rebuild(st, deadline, mode=0, seg_cursor=0):
        """Joint multi-satellite segment DP (rubric: segment_dp_heavy_ejection).

        (a) Partition timeline into contiguous segments derived from H
        (45-90 min equivalent: H/8 clipped), score by unscheduled weight
        density per segment-hour, pick top segment (rotating by seg_cursor).
        (b) Pool 2-3 satellites with most compatible unscheduled opps in
        that segment, clear only segment incumbents on them, rebuild
        sequentially: DP pool per satellite mixes cleared incumbents and
        unscheduled candidates overlapping segment; tasks not chosen on
        one satellite remain available to the next pooled satellite.
        (d) Accept only on strictly positive exact fast_N delta + sim.check.
        Battery: every insertion via try_insert (incremental battery_ok).
        """
        if time.time() > deadline:
            return None, -1.0, seg_cursor
        seg_len = min(5400.0, max(2700.0, H / 8.0))
        n_seg = max(1, int(H // seg_len) + (1 if H % seg_len else 0))
        # unscheduled weight density per segment (one count per task/segment)
        seg_weight = [0.0] * n_seg
        seg_sat_tasks = [dict() for _ in range(n_seg)]  # seg -> sat -> set tasks
        for t in tasks_by_weight:
            if t in st['done']:
                continue
            seen_seg = set()
            for k in opps_by_task[t]:
                if end_l[k] < 0 or start_l[k] >= H:
                    continue
                sidx = int(start_l[k] // seg_len)
                if sidx >= n_seg:
                    sidx = n_seg - 1
                seg_sat_tasks[sidx].setdefault(sat_l[k], set()).add(t)
                if sidx not in seen_seg:
                    seen_seg.add(sidx)
                    seg_weight[sidx] += task_weight[t]
        if not any(seg_weight):
            return None, -1.0, seg_cursor
        order_seg = sorted(range(n_seg), key=lambda s: (-(seg_weight[s] / max(1.0, seg_len / 3600.0)), s))
        top = order_seg[:min(3, n_seg)]
        sidx = top[seg_cursor % len(top)]
        seg_cursor += 1
        lo = sidx * seg_len
        hi = min(H, lo + seg_len)
        sat_counts = seg_sat_tasks[sidx]
        if not sat_counts:
            return None, -1.0, seg_cursor
        pooled = sorted(sat_counts.keys(), key=lambda si: (-len(sat_counts[si]), si))[:3]
        if len(pooled) < 2:
            return None, -1.0, seg_cursor
        cand_state = copy_state(st)
        cleared = []  # opp indices cleared from segment on pooled sats
        for si in pooled:
            for k in list(cand_state['chains'][si]):
                if lo <= start_l[k] < hi:
                    cleared.append(k)
        cleared_tasks = [task_l[k] for k in cleared]
        for k in cleared:
            remove_opp(cand_state, k)
        cleared_by_sat = {si: [k for k in cleared if sat_l[k] == si] for si in pooled}
        # Sequential DP over pooled satellites
        for si in pooled:
            if time.time() > deadline:
                break
            pool = []
            in_pool_tasks = set()
            # cleared incumbents for this satellite first
            for k in cleared_by_sat.get(si, []):
                t = task_l[k]
                if t not in cand_state['done'] and t not in in_pool_tasks:
                    pool.append(k)
                    in_pool_tasks.add(t)
            # unscheduled candidates overlapping segment, heaviest/densest first:
            # best opp per task on this satellite in segment
            best_per = {}
            for k in opps_by_sat_time[si]:
                if start_l[k] >= hi or end_l[k] <= lo:
                    continue
                t = task_l[k]
                if t in cand_state['done']:
                    continue
                cur = best_per.get(t)
                if cur is None or dens_l[k] > dens_l[cur]:
                    best_per[t] = k
            cand_list = sorted(best_per.values(), key=lambda kk: (-task_weight[task_l[kk]], -dens_l[kk], start_l[kk], kk))
            for k in cand_list[:240]:
                t = task_l[k]
                if t in in_pool_tasks or t in cand_state['done']:
                    continue
                pool.append(k)
                in_pool_tasks.add(t)
                if len(pool) >= 260:
                    break
            chain = _dp_chain_from_pool(pool, mode)
            for k in chain:
                try_insert(cand_state, k)
        # cross-satellite reinsertion of cleared tasks not yet placed
        for t in cleared_tasks:
            if t in cand_state['done']:
                continue
            for k in opps_by_task[t][:6]:
                if try_insert(cand_state, k):
                    break
        extra = []
        for t in tasks_by_prio:
            if t not in cand_state['done']:
                extra.append(t)
            if len(extra) >= 60:
                break
        repair(cand_state, extra, deadline, max_opps=4)
        sc = fast_N(cand_state)
        if sc > fast_N(st) + 1e-9 and full_valid(sorted(cand_state['chosen'])):
            return cand_state, sc, seg_cursor
        return None, -1.0, seg_cursor

    def heavy_ejection_chain(st, deadline, task_cursor, max_attempts=28):
        """Depth-up-to-3 heavy-first ejection chains.

        For heaviest unscheduled tasks, iteratively (depth 1..3) eject the
        lowest weight-per-occupied-time (dens_l) incumbents blocking the
        candidate on its satellite, insert candidate via try_insert
        (incremental slew+battery), then attempt cross-satellite
        reinsertion of every ejected task on any satellite. Accept only
        on strictly positive exact fast_N delta + sim.check.
        """
        cur = st
        cur_sc = fast_N(cur)
        attempts = 0
        order = tasks_by_weight[task_cursor:] + tasks_by_weight[:task_cursor]
        next_cursor = task_cursor
        for t in order:
            if attempts >= max_attempts or time.time() > deadline:
                break
            next_cursor = (next_cursor + 1) % max(1, n_tasks)
            if t in cur['done']:
                continue
            for k in opps_by_task[t][:6]:
                if attempts >= max_attempts or time.time() > deadline:
                    break
                cand = copy_state(cur)
                ejected = []
                inserted = False
                for _depth in range(3):  # depth up to 3 ejection layers
                    if try_insert(cand, k):
                        inserted = True
                        break
                    si = sat_l[k]
                    chain = cand['chains'][si]
                    starts = cand['starts'][si]
                    if not chain:
                        break
                    pos = bisect.bisect_left(starts, start_l[k])
                    blockers = []
                    if pos > 0:
                        b = chain[pos - 1]
                        if end_l[b] > start_l[k] + 1e-9 or start_l[k] - end_l[b] + 1e-9 < gap(b, k):
                            blockers.append(b)
                    if pos < len(chain):
                        b = chain[pos]
                        if end_l[k] > start_l[b] + 1e-9 or start_l[b] - end_l[k] + 1e-9 < gap(k, b):
                            blockers.append(b)
                    if not blockers:
                        break
                    # eject lowest density blockers first; gate: candidate
                    # must beat ejected density on value or density
                    blockers.sort(key=lambda bb: (dens_l[bb], bb))
                    victim = blockers[0]
                    if val_l[k] < 0.85 * val_l[victim] and dens_l[k] < dens_l[victim]:
                        break
                    ejected.append(task_l[victim])
                    remove_opp(cand, victim)
                attempts += 1
                if not inserted:
                    if not try_insert(cand, k):
                        continue
                # cross-satellite reinsertion of displaced tasks
                for et in ejected:
                    if et in cand['done']:
                        continue
                    placed = False
                    for ek in opps_by_task[et][:6]:
                        if try_insert(cand, ek):
                            placed = True
                            break
                    if not placed:
                        # second-level: try ejecting one very low density
                        # blocker on another satellite for this ejected task
                        for ek in opps_by_task[et][:4]:
                            si2 = sat_l[ek]
                            ch = cand['chains'][si2]
                            if not ch:
                                continue
                            sts = cand['starts'][si2]
                            pp = bisect.bisect_left(sts, start_l[ek])
                            bl = []
                            if pp > 0:
                                bl.append(ch[pp - 1])
                            if pp < len(ch):
                                bl.append(ch[pp])
                            bl = [b for b in bl if dens_l[b] < dens_l[ek] * 0.9]
                            if not bl:
                                continue
                            saved = copy_state(cand)
                            v = min(bl, key=lambda bb: dens_l[bb])
                            vt = task_l[v]
                            remove_opp(cand, v)
                            if try_insert(cand, ek):
                                ejected.append(vt)
                                placed = True
                                break
                            cand = saved
                            break
                sc = fast_N(cand)
                if sc > cur_sc + 1e-9 and full_valid(sorted(cand['chosen'])):
                    cur = cand
                    cur_sc = sc
                    break
        return cur, cur_sc, next_cursor

    # One deterministic widened chain-DP pass over all satellites.
    for si in range(n_sat):
        if time.time() > lns_deadline:
            break
        cand, sc = apply_chain_dp(best_state, si, lns_deadline, mode=si % 3)
        if cand is not None and sc > best_score + 1e-9 and full_valid(sorted(cand['chosen'])):
            best_state = cand
            best_score = sc
    cur_state = copy_state(best_state)
    cur_score = best_score

    # ---- LNS + swaps improvement ----
    # World-derived unscheduled weight density drives DP batch size: denser
    # leftover weight gets wider/more frequent DP+ejection rounds.
    _done_w = sum(task_weight[t] for t in best_state['done'])
    unsched_density = (W_total - _done_w) / W_total if W_total > 0 else 0.0
    dp_batch = 5 if unsched_density > 0.30 else (4 if unsched_density > 0.20 else 3)
    eject_attempts = 60 if unsched_density > 0.30 else 46

    iteration = 0
    dp_sat_cursor = 0
    dp_mode_cursor = 0
    eject_cursor = 0
    seg_cursor = 0
    heavy_cursor = 0
    pool_offset = 0
    # Early segment+heavy pass before generic LNS consumes budget (~70%
    # of improvement budget allocated to segment DP + ejection below).
    for _seg_round in range(2):
        if time.time() > lns_deadline:
            break
        cand_s, sc_s, seg_cursor = segment_dp_rebuild(
            best_state, lns_deadline, mode=_seg_round % 3, seg_cursor=seg_cursor)
        if cand_s is not None and sc_s > best_score + 1e-9:
            best_state = cand_s
            best_score = sc_s
    cand_h, sc_h, heavy_cursor = heavy_ejection_chain(
        best_state, lns_deadline, heavy_cursor, max_attempts=24)
    if sc_h > best_score + 1e-9:
        best_state = cand_h
        best_score = sc_h
    cur_state = copy_state(best_state)
    cur_score = best_score
    while time.time() < lns_deadline:
        iteration += 1
        # ~70% segment DP + ejection chains, rest per-sat DP / generic LNS.
        mode = iteration % 4
        if mode == 0:
            cand_s, sc_s, seg_cursor = segment_dp_rebuild(
                cur_state, lns_deadline, mode=dp_mode_cursor % 3, seg_cursor=seg_cursor)
            dp_mode_cursor += 1
            if cand_s is not None and sc_s > cur_score + 1e-9:
                cur_state = cand_s
                cur_score = sc_s
                if sc_s > best_score:
                    best_state = copy_state(cand_s)
                    best_score = sc_s
            continue
        if mode == 2:
            # widened chain-DP round (round-robin satellites, cycling modes)
            for _ in range(dp_batch):
                if time.time() > lns_deadline:
                    break
                si = dp_sat_cursor % n_sat
                dp_sat_cursor += 1
                dp_mode = dp_mode_cursor % 3
                dp_mode_cursor += 1
                cand_dp, sc_dp = apply_chain_dp(cur_state, si, lns_deadline,
                                                mode=dp_mode)
                if (cand_dp is not None and sc_dp > cur_score + 1e-9
                        and full_valid(sorted(cand_dp['chosen']))):
                    cur_state = cand_dp
                    cur_score = sc_dp
                    if sc_dp > best_score:
                        best_state = copy_state(cand_dp)
                        best_score = sc_dp
            continue
        if mode == 1:
            # alternate heavy ejection chains and legacy cross-sat ejection
            if (iteration // 4) % 2 == 0:
                cand_ej, sc_ej, heavy_cursor = heavy_ejection_chain(
                    cur_state, lns_deadline, heavy_cursor, max_attempts=28)
            else:
                cand_ej, sc_ej, eject_cursor = cross_sat_ejection(
                    cur_state, lns_deadline, eject_cursor, max_attempts=eject_attempts)
            if sc_ej > cur_score + 1e-9:
                cur_state = cand_ej
                cur_score = sc_ej
                if sc_ej > best_score:
                    best_state = copy_state(cand_ej)
                    best_score = sc_ej
            continue
        if mode == 3 and (iteration // 4) % 2 == 0:
            cand_s, sc_s, seg_cursor = segment_dp_rebuild(
                cur_state, lns_deadline, mode=dp_mode_cursor % 3, seg_cursor=seg_cursor)
            dp_mode_cursor += 1
            if cand_s is not None and sc_s > cur_score + 1e-9:
                cur_state = cand_s
                cur_score = sc_s
                if sc_s > best_score:
                    best_state = copy_state(cand_s)
                    best_score = sc_s
            continue
        destroy_mode = (iteration // 4) % 4
        cand = copy_state(cur_state)
        chosen_list = list(cand['chosen'])
        if not chosen_list:
            break
        removed_tasks = []
        if destroy_mode == 0:
            # random destroy 5-15%
            frac = 0.05 + 0.10 * rng.random()
            m = max(1, int(len(chosen_list) * frac))
            victims = rng.sample(chosen_list, min(m, len(chosen_list)))
        elif destroy_mode == 1:
            # worst-contribution destroy
            scored = sorted(chosen_list, key=lambda kk: marginal_density(cand, kk))
            m = max(1, int(len(chosen_list) * 0.10))
            victims = scored[:m]
        elif destroy_mode == 2:
            # time-window destroy on a random satellite
            si = rng.randrange(n_sat)
            if cand['chains'][si]:
                centre = cand['chains'][si][rng.randrange(len(cand['chains'][si]))]
                lo, hi = start_l[centre] - 3600.0, start_l[centre] + 3600.0
                victims = [kk for kk in cand['chains'][si] if lo <= start_l[kk] <= hi]
                if len(victims) > 40:
                    victims = victims[:40]
            else:
                victims = rng.sample(chosen_list, min(10, len(chosen_list)))
        else:
            # swap-oriented destroy: few low-density victims
            scored = sorted(chosen_list, key=lambda kk: marginal_density(cand, kk))
            victims = scored[:max(1, int(len(chosen_list) * 0.05))]
        for k in victims:
            removed_tasks.append(task_l[k])
            remove_opp(cand, k)

        # repair pool: removed first (regret order), then rotating unchosen tasks
        pool = sorted(set(removed_tasks), key=lambda t: (-task_best_prio[t], t))
        extra_pool = []
        scanned = 0
        j = pool_offset
        while scanned < n_tasks and len(extra_pool) < 180:
            t = tasks_by_prio[j % n_tasks]
            j += 1
            scanned += 1
            if t not in cand['done'] and t not in pool:
                extra_pool.append(t)
        pool_offset = j % max(1, n_tasks)
        repair(cand, pool + extra_pool, lns_deadline)

        # 1-for-1 / 1-for-2 swaps: replace a low-value chosen task with a
        # higher-value unchosen task on the same satellite (repair may then
        # add a second task into the freed space, giving 1-for-2).
        if destroy_mode == 3:
            cand2 = copy_state(cand)
            swaps_done = 0
            for t in extra_pool[:40]:
                if swaps_done >= 12 or time.time() > lns_deadline:
                    break
                if t in cand2['done']:
                    continue
                for k in opps_by_task[t][:5]:
                    si = sat_l[k]
                    chain = cand2['chains'][si]
                    starts = cand2['starts'][si]
                    pos = bisect.bisect_left(starts, start_l[k])
                    blockers = []
                    if pos > 0:
                        blockers.append(chain[pos - 1])
                    if pos < len(chain):
                        blockers.append(chain[pos])
                    blockers = [b for b in blockers if task_l[b] != t]
                    if len(blockers) != 1:
                        continue
                    b = blockers[0]
                    if task_weight[t] <= task_weight[task_l[b]] * 1.0:
                        continue
                    saved = copy_state(cand2)
                    remove_opp(cand2, b)
                    if try_insert(cand2, k):
                        swaps_done += 1
                        break
                    cand2 = saved
            if fast_N(cand2) > fast_N(cand):
                cand = cand2

        sc = fast_N(cand)
        if sc > cur_score + 1e-9:
            cur_state = cand
            cur_score = sc
            if sc > best_score:
                best_state = copy_state(cand)
                best_score = sc
        # else revert to cur_state (candidate discarded)

    # ---- final validation with sim.check + deterministic fallback ----
    def validated(selection):
        try:
            rep = sim.check(world, list(selection))
            return bool(rep.get('valid'))
        except Exception:
            return False

    selection = sorted(best_state['chosen'])
    if not validated(selection):
        # drop lowest-contribution observations until valid
        work_state = copy_state(best_state)
        guard = 0
        while selection and guard < 500 and time.time() < hard_deadline:
            guard += 1
            scored = sorted(selection, key=lambda kk: marginal_density(work_state, kk))
            victim = scored[0]
            remove_opp(work_state, victim)
            selection = sorted(work_state['chosen'])
            if validated(selection):
                break
        if not validated(selection):
            # baseline earliest-fit feasible subset as final fallback
            fb = new_state()
            border = sorted(range(n), key=lambda kk: (start_l[kk], sat_l[kk], kk))
            for k in border:
                if task_l[k] in fb['done']:
                    continue
                try_insert(fb, k)
                if (len(fb['chosen']) & 1023) == 0 and time.time() > hard_deadline:
                    break
            selection = sorted(fb['chosen'])
            work_state = fb
            guard = 0
            while selection and not validated(selection) and guard < 500:
                guard += 1
                scored = sorted(selection, key=lambda kk: marginal_density(work_state, kk))
                remove_opp(work_state, scored[0])
                selection = sorted(work_state['chosen'])
                if time.time() > hard_deadline:
                    break
    return [int(k) for k in selection]
