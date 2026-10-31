"""Battery-aware weighted greedy with repair and local search.

Contention-priced construction: per-task opportunity scarcity and per
 satellite-time-bucket contention are computed from the supplied world;
 2-3 deterministic priced restarts order tasks scarcity-then-weight,
 insert each at the feasible opportunity minimising congestion price plus
 slew-gap cost, and update bucket prices between restarts.  Priced plans
 and the unmodified seed constructions compete by exact whole-plan score;
 priced construction is capped at 25% of the internal deadline and at
 least 70% of the remaining budget is devoted to iterated ejection.
Construction: several deterministic best-insertion greedy passes ordered by
weight / earliness / turnaround / scarcity / duration trade-offs.  Every
insertion checks, before acceptance:
  * non-overlap plus sim.required_gap_s against predecessor and successor
    (nadir_slew_s for a first observation), with gaps cached, and
  * a conservative battery-nonnegative condition: an idle-only battery
    trajectory B0(t) (sunlit charging, capacity cap, mirroring sim.check)
    minus a suffix profile of all committed imaging+slew energy must stay
    above a per-satellite safety reserve at every sunlit sample.
Perturbed iterated ejection: weight-first 1-for-1/1-for-2 (and 1-for-3 for
 the heaviest unscheduled decile) ejection rounds run until an internal
 deadline, with deterministic perturbation kicks (low weight-per-occupied-
 time removals plus temporal neighbours, regret repair, restart-from-best-
 ever) and a cumulative turnaround budget cap derived from the seed plan.
Improvement: exact internal scorer (mirroring WCR/CR/TAT/PC in sim.check)
 drives prune and a deadline-driven adaptive large-neighbourhood search
(five destroy operators, regret-2 repair by exact marginal score delta,
1-for-1 / 1-for-2 swap-ejection, same-task re-timing, adaptive operator
weights, best-so-far tracking and restart-from-best on stagnation) run
until a deadline derived from time_limit_s.  A final sim.check validates
the returned plan, with a chronological battery-safe plan as fallback.
Only world / sim / numpy / stdlib are used; all seeds are fixed and all
thresholds are derived from the supplied world.
"""
import bisect
import math
import random
import time

import numpy as np
import sim


def solve(world, time_limit_s):
    random.seed(0)
    np.random.seed(0)
    t0 = time.time()
    tl = float(time_limit_s) if time_limit_s else 60.0
    _budget = min(0.85 * tl, 52.0)
    if tl > 8.0:
        _budget = min(_budget, tl - 5.0)
    # Budget split: priced + seed constructions capped at 25% of the
    # internal budget, a brief ALNS phase to 40%, and perturbed iterated
    # ejection from 40% to 97% -- i.e. ejection receives >=70% of the
    # budget remaining after priced construction (0.57/0.75 = 76%).
    priced_deadline = t0 + max(1.0, _budget * 0.25)
    search_deadline = priced_deadline
    ejection_deadline = t0 + max(2.0, _budget * 0.97)
    final_deadline = t0 + max(2.0, tl - 3.0)

    sat_a = np.asarray(world['sat']).astype(int)
    task_a = np.asarray(world['task']).astype(int)
    start_a = np.asarray(world['start_s']).astype(float)
    end_a = np.asarray(world['end_s']).astype(float)
    nadir_a = np.asarray(world['nadir_slew_s']).astype(float)
    n = int(len(sat_a))
    if n == 0:
        return []
    tasks = world['tasks']
    n_tasks = len(tasks)
    w_task = np.array([float(t['weight']) for t in tasks], dtype=float)
    release_a = np.array([float(t['release_s']) for t in tasks], dtype=float)
    total_w = float(np.sum(w_task)) or 1.0
    horizon = float(world['horizon_s']) or 1.0
    e_budget = float(world.get('energy_budget_wh') or
                     sum(float(s['battery_capacity_wh']) for s in world['satellites'])) or 1.0
    sats = world['satellites']
    n_sat = len(sats)
    idle_p = np.array([float(s['idle_power_w']) for s in sats])
    img_p = np.array([float(s['imaging_power_w']) for s in sats])
    slew_p = np.array([float(s['slew_power_w']) for s in sats])
    cap_a = np.array([float(s['battery_capacity_wh']) for s in sats])
    sunlit = np.asarray(world['sunlit']).astype(bool)
    step = int(world['sunlit_step_s']) or 60
    n_steps = int(sunlit.shape[1]) if sunlit.ndim == 2 and sunlit.shape[1] else 1
    reserve = 0.01 * cap_a + 0.3
    idle_const_pc = float(np.sum(idle_p)) * horizon / 3600.0

    # Idle-only battery trajectory B0 per satellite (mirrors sim.check:
    # charge when sunlit, idle load always, cap at capacity).
    b0_list = []
    for si in range(n_sat):
        arr = np.empty(n_steps, dtype=float)
        bat = float(sats[si]['initial_battery_wh'])
        cap = float(sats[si]['battery_capacity_wh'])
        charge = float(sats[si]['sunlit_charge_power_w'])
        idle = float(idle_p[si])
        row = sunlit[si] if si < sunlit.shape[0] else np.zeros(n_steps, bool)
        for i in range(n_steps):
            arr[i] = bat
            d = ((charge if row[i] else 0.0) - idle) * step / 3600.0
            bat += d
            if bat > cap:
                bat = cap
        b0_list.append(arr)

    gap_cache = {}

    def gap(i, j):
        key = (int(i), int(j))
        v = gap_cache.get(key)
        if v is None:
            v = float(sim.required_gap_s(world, int(i), int(j)))
            gap_cache[key] = v
        return v

    class State:
        __slots__ = ('timelines', 'starts', 'margin', 'done', 'gap_before',
                     'dval', 'done_w', 'cnt', 'sum_tat', 'pc_extra')

        def __init__(self):
            self.timelines = [[] for _ in range(n_sat)]
            self.starts = [[] for _ in range(n_sat)]
            self.margin = [b.copy() for b in b0_list]
            self.done = np.zeros(n_tasks, dtype=bool)
            self.gap_before = np.full(n, np.nan)
            self.dval = np.zeros(n, dtype=float)
            self.done_w = 0.0
            self.cnt = 0
            self.sum_tat = 0.0
            self.pc_extra = 0.0

        def score(self):
            if self.cnt == 0:
                return -1.0
            cl = lambda x: min(1.0, max(0.0, x))
            tat = self.sum_tat / self.cnt
            pc = idle_const_pc + self.pc_extra
            return 100.0 * (0.45 * self.done_w / total_w + 0.20 * self.cnt / n_tasks
                            + 0.20 * cl(1.0 - tat / horizon) + 0.15 * cl(1.0 - pc / e_budget))

        def selection(self):
            out = []
            for lst in self.timelines:
                out.extend(lst)
            return out

        def trial(self, k):
            s = int(sat_a[k])
            lst = self.timelines[s]
            stl = self.starts[s]
            st = float(start_a[k]); en = float(end_a[k])
            pos = bisect.bisect_left(stl, st)
            pred = lst[pos - 1] if pos > 0 else None
            succ = lst[pos] if pos < len(lst) else None
            if pred is None:
                need = float(nadir_a[k])
                if st + 1e-9 < need:
                    return None
            else:
                need = gap(pred, k)
                if st - float(end_a[pred]) + 1e-9 < need:
                    return None
            delta_d_succ = 0.0
            need_succ_new = None
            if succ is not None:
                need_succ_new = gap(k, succ)
                if float(start_a[succ]) - en + 1e-9 < need_succ_new:
                    return None
                delta_d_succ = float(slew_p[s]) * (need_succ_new - float(self.gap_before[succ])) / 3600.0
            d_k = float(img_p[s]) * (en - st) / 3600.0 + float(slew_p[s]) * need / 3600.0
            s_idx = int(st // step)
            if s_idx < 0:
                s_idx = 0
            elif s_idx >= n_steps:
                s_idx = n_steps - 1
            marg = self.margin[s]
            worst = float(np.min(marg[s_idx:])) - d_k - (delta_d_succ if delta_d_succ > 0.0 else 0.0)
            if worst + 1e-9 < float(reserve[s]):
                return None
            return (s, pos, succ, need, need_succ_new, delta_d_succ, d_k, s_idx)

        def commit(self, k, tr):
            s, pos, succ, need, need_succ_new, delta_d_succ, d_k, s_idx = tr
            marg = self.margin[s]
            marg[s_idx:] -= d_k
            if succ is not None:
                succ_idx = int(float(start_a[succ]) // step)
                succ_idx = min(max(succ_idx, 0), n_steps - 1)
                marg[succ_idx:] -= delta_d_succ
                self.gap_before[succ] = need_succ_new
                self.dval[succ] += delta_d_succ
            self.timelines[s].insert(pos, int(k))
            self.starts[s].insert(pos, float(start_a[k]))
            self.gap_before[k] = need
            self.dval[k] = d_k
            t = int(task_a[k])
            self.done[t] = True
            self.done_w += float(w_task[t])
            self.cnt += 1
            self.sum_tat += float(end_a[k]) - float(release_a[t])
            self.pc_extra += d_k + delta_d_succ

        def remove(self, k):
            k = int(k)
            s = int(sat_a[k])
            lst = self.timelines[s]
            try:
                pos = lst.index(k)
            except ValueError:
                return
            pred = lst[pos - 1] if pos > 0 else None
            succ = lst[pos + 1] if pos + 1 < len(lst) else None
            d_r = float(self.dval[k])
            r_idx = int(float(start_a[k]) // step)
            r_idx = min(max(r_idx, 0), n_steps - 1)
            marg = self.margin[s]
            marg[r_idx:] += d_r
            delta = 0.0
            if succ is not None:
                need_new = float(nadir_a[succ]) if pred is None else gap(pred, succ)
                delta = float(slew_p[s]) * (need_new - float(self.gap_before[succ])) / 3600.0
                succ_idx = int(float(start_a[succ]) // step)
                succ_idx = min(max(succ_idx, 0), n_steps - 1)
                marg[succ_idx:] -= delta
                self.gap_before[succ] = need_new
                self.dval[succ] += delta
            del lst[pos]
            del self.starts[s][pos]
            self.gap_before[k] = np.nan
            self.dval[k] = 0.0
            t = int(task_a[k])
            self.done[t] = False
            self.done_w -= float(w_task[t])
            self.cnt -= 1
            self.sum_tat -= float(end_a[k]) - float(release_a[t])
            self.pc_extra += -d_r + delta

    def build(sel):
        st = State()
        for k in sorted((int(x) for x in sel), key=lambda x: float(start_a[x])):
            if st.done[int(task_a[k])]:
                continue
            tr = st.trial(k)
            if tr is not None:
                st.commit(k, tr)
        return st

    # ---- candidate orderings -------------------------------------------------
    dur = end_a - start_a
    tat_arr = end_a - release_a[task_a]
    w_opp = w_task[task_a]
    opp_cnt = np.bincount(task_a, minlength=n_tasks)[task_a].astype(float)

    def rank_pct(values):
        order = np.argsort(values, kind='stable')
        r = np.empty(n, dtype=float)
        r[order] = np.arange(n, dtype=float)
        return r / max(1, n - 1)

    p_w = rank_pct(w_opp)
    p_early = 1.0 - rank_pct(start_a)
    p_tat = 1.0 - rank_pct(tat_arr)
    med_dur = float(np.median(dur)) if n else 1.0
    cost = ((dur + 15.0) / (med_dur + 15.0))
    scarcity = 1.0 / np.sqrt(np.maximum(1.0, opp_cnt))

    orders = []
    orders.append(np.lexsort((-w_opp, start_a)))  # chronological (fallback)
    variant_specs = [
        (1.0, 0.4, 0.0, 0.0, 0.3),
        (0.6, 0.8, 0.0, 0.0, 0.3),
        (1.5, 0.2, 0.3, 0.5, 0.5),
        (0.4, 1.0, 0.3, 0.0, 0.0),
        (0.9, 0.6, 0.6, 0.3, 0.5),
    ]
    cand_score = None
    for (aw, ae, at, ce, se) in variant_specs:
        sc = (aw * p_w + ae * p_early + at * p_tat) / np.power(cost, ce) * np.power(scarcity, se * 2.0)
        if cand_score is None:
            cand_score = sc
        orders.append(np.argsort(-sc, kind='stable'))
    cand_order = [int(x) for x in np.argsort(-(0.9 * p_w + 0.6 * p_early + 0.6 * p_tat)
                                             / np.power(cost, 0.3) * scarcity, kind='stable')]

    def construct(order):
        st = State()
        cnt_iter = 0
        for kk in order:
            cnt_iter += 1
            if (cnt_iter & 4095) == 0 and time.time() > search_deadline:
                break
            k = int(kk)
            if st.done[int(task_a[k])]:
                continue
            tr = st.trial(k)
            if tr is not None:
                st.commit(k, tr)
        return st

    # ---- contention-priced construction (from the supplied world only) -----
    opps_by_task_pre = [[] for _ in range(n_tasks)]
    for _k in range(n):
        opps_by_task_pre[int(task_a[_k])].append(int(_k))
    opp_cnt_task = np.bincount(task_a, minlength=n_tasks).astype(float)
    distinct_sat = np.zeros(n_tasks, dtype=float)
    _sat_sets = [set() for _ in range(n_tasks)]
    for _k in range(n):
        _sat_sets[int(task_a[_k])].add(int(sat_a[_k]))
    for _t in range(n_tasks):
        distinct_sat[_t] = float(len(_sat_sets[_t]))
    # Satellite-time buckets (width derived from the horizon) and contention:
    # total normalised task weight competing for each bucket.
    bucket_width = max(300.0, horizon / 72.0)
    n_buckets = int(math.ceil(horizon / bucket_width)) or 1
    bucket_of = (sat_a * n_buckets
                 + np.minimum(n_buckets - 1,
                              (start_a // bucket_width).astype(int))).astype(int)
    contention = np.zeros(n_sat * n_buckets, dtype=float)
    np.add.at(contention, bucket_of, w_opp / np.maximum(1.0, opp_cnt))
    _pos = contention[contention > 0.0]
    price0 = contention / (float(np.mean(_pos)) if _pos.size else 1.0)
    # Per-task scarcity: few feasible opportunities / distinct satellites
    # first, then descending weight (scarcity-then-weight ordering).
    priced_task_order = sorted(
        range(n_tasks),
        key=lambda t: (float(opp_cnt_task[t]), float(distinct_sat[t]),
                       -float(w_task[t]), float(release_a[t])))

    def priced_construct(price):
        st = State()
        for ti, t in enumerate(priced_task_order):
            if (ti & 127) == 0 and time.time() > priced_deadline:
                break
            if st.done[t]:
                continue
            # Feasible opportunity minimising congestion price plus a
            # slew-gap / earliness proxy; feasibility (non-overlap, required
            # slew gap, battery) is checked by State.trial before commit.
            opps = sorted(
                opps_by_task_pre[t],
                key=lambda k: (float(price[int(bucket_of[k])])
                               + 0.001 * float(nadir_a[k])
                               + 0.10 * float(start_a[k]) / horizon,
                               float(start_a[k])))
            for k in opps:
                tr = st.trial(int(k))
                if tr is not None:
                    st.commit(int(k), tr)
                    break
        return st

    def update_prices(price, st, step_size):
        # Dual-style update: raise prices where scheduled load exceeded
        # 60% of bucket capacity, lower them where slack remains.
        load = np.zeros(n_sat * n_buckets, dtype=float)
        _sel = st.selection()
        if _sel:
            np.add.at(load, bucket_of[_sel], (end_a - start_a)[_sel])
        load = load / bucket_width
        new_price = price * (1.0 + step_size * (load - 0.6))
        return np.clip(new_price, 0.02, 20.0)

    best_state = None
    fallback_sel = []

    def consider(st):
        nonlocal best_state
        if best_state is None or st.score() > best_state.score():
            best_state = st

    # Unmodified cycle-4 chronological seed first (fallback + competitor).
    _seed0 = construct(orders[0])
    fallback_sel = _seed0.selection()
    consider(_seed0)
    # 2-3 deterministic priced restarts with fixed price-update steps.
    _price = price0.copy()
    for _r, _step in enumerate((0.8, 0.5, 0.3)):
        if time.time() > priced_deadline:
            break
        _pst = priced_construct(_price)
        consider(_pst)
        if _r < 2:
            _price = update_prices(_price, _pst, _step)
    # Remaining unmodified seed constructions compete on exact score.
    for oi, order in enumerate(orders[1:], start=1):
        if time.time() > priced_deadline:
            break
        consider(construct(order))

    state = best_state if best_state is not None else State()
    # Brief ALNS diversification; ejection (below) is protected thereafter.
    search_deadline = t0 + max(2.0, _budget * 0.40)

    def prune_pass(st):
        for k in list(st.selection()):
            if time.time() > search_deadline:
                break
            before = st.score()
            st.remove(k)
            if st.score() <= before + 1e-12:
                tr = st.trial(k)
                if tr is not None:
                    st.commit(k, tr)

    def insertion_pass(st):
        improved = False
        for k in cand_order:
            if time.time() > search_deadline:
                break
            if st.done[int(task_a[k])]:
                continue
            tr = st.trial(k)
            if tr is None:
                continue
            before = st.score()
            st.commit(k, tr)
            if st.score() > before + 1e-12:
                improved = True
            else:
                st.remove(k)
        return improved

    prune_pass(state)
    insertion_pass(state)

    # ---- deadline-driven adaptive regret LNS ---------------------------------
    opps_by_task = [[] for _ in range(n_tasks)]
    for _k in range(n):
        opps_by_task[int(task_a[_k])].append(int(_k))

    def exact_delta(st, k, tr):
        # Exact marginal mission-score delta of inserting k (state unchanged).
        _s, _pos, _succ, _need, _nsn, delta_d_succ, d_k, _sidx = tr
        t = int(task_a[k])
        cl = lambda x: min(1.0, max(0.0, x))
        cnt2 = st.cnt + 1
        tat2 = (st.sum_tat + float(end_a[k]) - float(release_a[t])) / cnt2
        pc2 = idle_const_pc + st.pc_extra + d_k + delta_d_succ
        after = 100.0 * (0.45 * (st.done_w + float(w_task[t])) / total_w
                         + 0.20 * cnt2 / n_tasks
                         + 0.20 * cl(1.0 - tat2 / horizon)
                         + 0.15 * cl(1.0 - pc2 / e_budget))
        return after - st.score()

    def regret_repair(st, priority_tasks, scan_offset):
        # Regret-2 repair: one shortlist scan finds, per undone task, the
        # best and second-best exact marginal delta; tasks are then inserted
        # in order of decreasing (best - second-best) regret, re-checked
        # exactly (gap + battery via trial) before every commit.
        scan = []
        for t in priority_tasks:
            scan.extend(opps_by_task[int(t)])
        if cand_order:
            seg = cand_order[scan_offset:scan_offset + 12000]
            scan.extend(seg)
            if len(seg) < 4000:
                scan.extend(cand_order[:4000 - len(seg)])
        best1 = {}
        best2 = {}
        checked = 0
        for k in scan:
            checked += 1
            if (checked & 2047) == 0 and time.time() > search_deadline:
                break
            t = int(task_a[k])
            if st.done[t]:
                continue
            tr = st.trial(k)
            if tr is None:
                continue
            d = exact_delta(st, k, tr)
            prev = best1.get(t)
            if prev is None or d > prev[0]:
                if prev is not None:
                    best2[t] = prev
                best1[t] = (d, int(k))
            else:
                sec = best2.get(t)
                if sec is None or d > sec[0]:
                    best2[t] = (d, int(k))
        if not best1:
            return False

        def regret_key(item):
            t, pair = item
            sec = best2.get(t)
            regret = (pair[0] - sec[0]) if sec is not None else pair[0] + 0.005
            return (regret, pair[0])

        improved = False
        for t, pair in sorted(best1.items(), key=regret_key, reverse=True):
            if time.time() > search_deadline:
                break
            if st.done[t]:
                continue
            k = int(pair[1])
            tr = st.trial(k)
            if tr is None:
                # Fall back to the second-best opportunity for this task.
                sec = best2.get(t)
                if sec is None:
                    continue
                k = int(sec[1])
                tr = st.trial(k)
                if tr is None:
                    continue
            if exact_delta(st, k, tr) > 1e-12:
                st.commit(k, tr)
                improved = True
        return improved

    def restore_one(st, k):
        tr = st.trial(k)
        if tr is not None:
            st.commit(k, tr)
            return True
        return False

    def swap_pass(st, attempts_limit):
        # 1-for-1 swaps, extended to 1-for-2 when the ejected task can be
        # re-inserted at another opportunity after the swap.
        attempts = 0
        scanned = 0
        improved_any = False
        for k in cand_order:
            if attempts >= attempts_limit or scanned >= 6000:
                break
            if time.time() > search_deadline:
                break
            scanned += 1
            t = int(task_a[k])
            if st.done[t]:
                continue
            if st.trial(k) is not None:
                continue
            s = int(sat_a[k])
            lst = st.timelines[s]
            if not lst:
                continue
            pos = bisect.bisect_left(st.starts[s], float(start_a[k]))
            blockers = []
            if pos > 0:
                blockers.append(int(lst[pos - 1]))
            if pos < len(lst):
                blockers.append(int(lst[pos]))
            if not blockers:
                continue
            attempts += 1
            before_score = st.score()
            for blocker in blockers:
                bt = int(task_a[blocker])
                st.remove(blocker)
                tr = st.trial(k)
                if tr is None:
                    restore_one(st, blocker)
                    continue
                st.commit(k, tr)
                inserted = [int(k)]
                for alt in opps_by_task[bt]:
                    if st.done[bt]:
                        break
                    if int(alt) == blocker:
                        continue
                    tra = st.trial(int(alt))
                    if tra is not None and exact_delta(st, int(alt), tra) > 1e-12:
                        st.commit(int(alt), tra)
                        inserted.append(int(alt))
                        break
                if st.score() > before_score + 1e-12:
                    improved_any = True
                    break
                for ins in reversed(inserted):
                    st.remove(ins)
                restore_one(st, blocker)
        return improved_any

    def retime_pass(st, offset, count):
        # Same-task re-timing: move a scheduled observation to another
        # opportunity of the same task only if the exact score improves.
        sel = st.selection()
        if not sel:
            return False
        improved = False
        seen = set()
        subset = []
        idx = 0
        while len(subset) < min(count, len(sel)) and idx < len(sel) * 2:
            cand = int(sel[(offset + idx * 7) % len(sel)])
            idx += 1
            if cand not in seen:
                seen.add(cand)
                subset.append(cand)
        for k in subset:
            if time.time() > search_deadline:
                break
            s = int(sat_a[k])
            if k not in st.timelines[s]:
                continue
            t = int(task_a[k])
            before_score = st.score()
            st.remove(k)
            removed_score = st.score()
            best_alt = None
            best_final = before_score
            for alt in opps_by_task[t]:
                tra = st.trial(int(alt))
                if tra is None:
                    continue
                final = removed_score + exact_delta(st, int(alt), tra)
                if final > best_final + 1e-12:
                    best_final = final
                    best_alt = int(alt)
            if best_alt is not None:
                tra = st.trial(best_alt)
                if tra is not None:
                    st.commit(best_alt, tra)
                    improved = True
                elif not restore_one(st, k):
                    restore_one(st, k)
            else:
                restore_one(st, k)
        return improved

    def destroy_victims(st, op, size, rnd_idx, rng):
        sel = st.selection()
        if not sel:
            return []
        size = max(1, min(int(size), len(sel)))
        if op == 0:
            # Worst exact-score-efficiency observations.
            def eff(k):
                t = int(task_a[k])
                gain = 0.45 * float(w_task[t]) / total_w + 0.20 / n_tasks
                return gain / (1.0 + max(0.0, float(end_a[k] - release_a[t])) / horizon)
            victims = sorted(sel, key=eff)[:size]
        elif op == 1:
            # Contiguous segment on one satellite.
            by_sat = {}
            for k in sel:
                by_sat.setdefault(int(sat_a[k]), []).append(int(k))
            sat_ids = sorted(by_sat.keys())
            s_pick = sat_ids[rng.randrange(len(sat_ids))]
            lst = by_sat[s_pick]
            if len(lst) <= size:
                victims = list(lst)
            else:
                start_pos = rng.randrange(len(lst) - size + 1)
                victims = lst[start_pos:start_pos + size]
        elif op == 2:
            # Time-window cluster across satellites.
            centre = float(start_a[int(sel[(rnd_idx * 37) % len(sel)])])
            victims = sorted(sel, key=lambda x: abs(float(start_a[x]) - centre))[:size]
        elif op == 3:
            # Related observations: nearby starts competing for overlapping
            # windows, preferring the same satellite neighbourhood.
            seed = int(sel[(rnd_idx * 53) % len(sel)])
            seed_start = float(start_a[seed])
            seed_sat = int(sat_a[seed])

            def rel(k):
                same = 0.0 if int(sat_a[k]) == seed_sat else horizon * 0.25
                return abs(float(start_a[k]) - seed_start) + same
            victims = sorted(sel, key=rel)[:size]
        else:
            # Deterministic pseudo-random removal (fixed-seed stream).
            victims = rng.sample(sel, size)
        return [int(x) for x in victims]

    rng_alns = random.Random(20261030)
    op_weights = [1.0, 1.0, 1.0, 1.0, 1.0]
    op_uses = [0, 0, 0, 0, 0]
    op_rewards = [0.0, 0.0, 0.0, 0.0, 0.0]
    destroy_base = [8, 14, 22, 10, 18, 28, 12, 36]
    best_sel = state.selection()
    best_score = state.score()
    stagnation = 0
    restart_boost = 0
    rnd = 0
    while time.time() < search_deadline:
        sel_before = state.selection()
        if not sel_before:
            break
        before_score = state.score()
        # Adaptive operator selection (deterministic weighted choice).
        total_wt = sum(op_weights)
        pick = rng_alns.random() * total_wt
        op = 0
        acc = 0.0
        for oi in range(len(op_weights)):
            acc += op_weights[oi]
            if pick <= acc:
                op = oi
                break
        size = destroy_base[rnd % len(destroy_base)] + restart_boost + (stagnation // 12) * 4
        size = max(4, min(40, size))
        victims = destroy_victims(state, op, size, rnd, rng_alns)
        freed_tasks = []
        seen_t = set()
        for k in victims:
            t = int(task_a[k])
            if t not in seen_t:
                seen_t.add(t)
                freed_tasks.append(t)
            state.remove(k)
        regret_repair(state, freed_tasks, (rnd * 12000) % max(1, len(cand_order)))
        if rnd % 3 == 0:
            swap_pass(state, 18)
        if rnd % 4 == 1:
            retime_pass(state, rnd * 11 + 3, 18)
        cand_score = state.score()
        gain = cand_score - before_score
        op_uses[op] += 1
        if gain > 1e-12:
            op_rewards[op] += 1.0 + 10.0 * gain
        if cand_score > best_score + 1e-12:
            best_score = cand_score
            best_sel = state.selection()
            stagnation = 0
            restart_boost = 0
        else:
            stagnation += 1
        if gain > 1e-12:
            pass  # exact-score improvement: keep
        elif cand_score > before_score - 0.03 and (rnd % 5 == 4):
            pass  # bounded deterministic reheating of the working plan
        else:
            state = build(sel_before)
        if stagnation >= 28:
            state = build(best_sel)
            stagnation = 0
            restart_boost = 12
        if (rnd % 20) == 19:
            for oi in range(len(op_weights)):
                if op_uses[oi] > 0:
                    op_weights[oi] = max(0.2, 0.7 * op_weights[oi]
                                         + op_rewards[oi] / op_uses[oi])
                op_uses[oi] = 0
                op_rewards[oi] = 0.0
        rnd += 1

    # ---- weight-first ejection chains (majority of the budget) --------------
    # Unscheduled tasks are processed in descending weight order (tie-break:
    # weight per duration, then earliest due).  Each candidate is inserted
    # freely if possible, otherwise by ejecting 1 or 2 incumbents with the
    # lowest weight-per-occupied-time on the same satellite.  Ejected tasks
    # get a depth-2 reinsertion attempt at their best other opportunity.
    # A move is kept only on a positive exact full-plan score delta that
    # also respects an explicit mean-turnaround tolerance (stricter late),
    # so weighted gains are not bought with turnaround regression.  Every
    # insertion / reinsertion goes through State.trial, i.e. the cached
    # slew-gap, sensor-opportunity and conservative battery-reserve checks.
    state = build(best_sel)
    if state.score() > best_score:
        best_score = state.score()
        best_sel = state.selection()
    search_deadline = ejection_deadline
    eject_start_tat = (state.sum_tat / state.cnt) if state.cnt else 0.0
    # Cumulative turnaround budget: cap derived from the seed (pre-ejection)
    # plan's mean TAT minus a world-derived margin.  Early moves get a small
    # allowance above the cap that shrinks to ~0 at the deadline, and any
    # move above cap+allowance is accepted only if it does not increase TAT
    # (the increase must be repaid by later TAT-non-increasing moves).
    tat_margin = max(6.0, 0.010 * eject_start_tat) if eject_start_tat else 6.0
    tat_cap = max(0.0, eject_start_tat - tat_margin)
    # CR floor: seed CR minus 0.002 (count-increasing recovery moves below
    # the floor are still allowed; best-ever updates enforce the floor).
    cr_floor_cnt = max(0, int(math.ceil((state.cnt / max(1, n_tasks) - 0.002) * n_tasks))) if state.cnt else 0
    heavy_cut = float(np.percentile(w_task, 90.0)) if n_tasks else 0.0
    world_seed = int((int(n) * 1315423911 + int(n_tasks) * 2654435761
                      + int(total_w * 1000.0) + int(horizon)) % 2147483647)

    def mean_tat(st):
        return (st.sum_tat / st.cnt) if st.cnt else 0.0

    def _deadline_frac():
        span = max(1.0, ejection_deadline - t0)
        return min(1.0, max(0.0, (time.time() - t0) / span))

    def tat_tol():
        frac = _deadline_frac()
        return 4.0 * (1.0 - frac) + 1.0 * frac  # 4 s early -> 1 s late

    def tat_allowance():
        frac = _deadline_frac()
        return 22.0 * (1.0 - frac) + 2.0 * frac

    def accept_ok(st, before_score, before_tat, before_cnt=None):
        if st.score() <= before_score + 1e-12:
            return False
        if st.cnt < cr_floor_cnt and before_cnt is not None and st.cnt <= before_cnt:
            return False
        mt = mean_tat(st)
        if mt > before_tat + tat_tol():
            return False
        # Hard cumulative budget (supersedes the old seed+20 cap).
        if mt > tat_cap + tat_allowance() and mt > before_tat - 1e-9:
            return False
        if mt > tat_cap + 24.0:
            return False
        return True

    def blockers_for(st, k):
        s = int(sat_a[k])
        lst = st.timelines[s]
        if not lst:
            return []
        pos = bisect.bisect_left(st.starts[s], float(start_a[k]))
        out = []
        for idx in range(max(0, pos - 3), min(len(lst), pos + 3)):
            inc = int(lst[idx])
            if float(end_a[inc]) <= float(start_a[k]):
                conf = float(start_a[k]) - float(end_a[inc]) < gap(inc, k) - 1e-9
            elif float(end_a[k]) <= float(start_a[inc]):
                conf = float(start_a[inc]) - float(end_a[k]) < gap(k, inc) - 1e-9
            else:
                conf = True
            if conf:
                out.append(inc)
        return out

    def occ_eff(k):
        t = int(task_a[k])
        gb = float(st_gap_before(k))
        occ = float(end_a[k] - start_a[k]) + (gb if gb == gb and gb > 0 else float(nadir_a[k]))
        return float(w_task[t]) / max(1.0, occ)

    def st_gap_before(k):
        return float(state.gap_before[int(k)])

    def ejection_pass(st):
        improved = False
        undone = [t for t in range(n_tasks) if not st.done[t]]
        undone.sort(key=lambda t: (-float(w_task[t]),
                                   -float(w_task[t]) / max(1.0, float(tasks[t]['duration_s'])),
                                   float(tasks[t]['due_s']), float(tasks[t]['release_s'])))
        attempts = 0
        for t in undone:
            if time.time() > search_deadline:
                break
            if st.done[t]:
                continue
            opps = sorted((int(x) for x in opps_by_task[t]),
                          key=lambda x: (float(end_a[x]) - float(release_a[t]),
                                         float(start_a[x])))
            is_heavy = float(w_task[t]) >= heavy_cut
            for k in opps[:(12 if is_heavy else 10)]:
                if time.time() > search_deadline:
                    break
                if st.done[t]:
                    break
                before_score = st.score()
                before_tat = mean_tat(st)
                before_cnt = st.cnt
                before_sel = None
                tr = st.trial(k)
                if tr is not None:
                    st.commit(k, tr)
                    if accept_ok(st, before_score, before_tat, before_cnt):
                        improved = True
                    else:
                        st.remove(k)
                    continue
                if attempts >= (1500 if is_heavy else 900):
                    continue
                bl = blockers_for(st, k)
                if not bl:
                    continue
                bl_sorted = sorted(bl, key=occ_eff)
                eject_sets = []
                for b in bl_sorted[:3]:
                    eject_sets.append([b])
                if len(bl_sorted) >= 2:
                    eject_sets.append(bl_sorted[:2])
                    pair = []
                    for b in bl:
                        if b not in pair:
                            pair.append(b)
                    if len(pair) >= 2 and pair[:2] != bl_sorted[:2]:
                        eject_sets.append(pair[:2])
                # 1-for-3 ejection reserved for the heaviest decile.
                if is_heavy and len(bl_sorted) >= 3:
                    eject_sets.append(bl_sorted[:3])
                for es in eject_sets:
                    if time.time() > search_deadline:
                        break
                    attempts += 1
                    before_sel = st.selection()
                    before_score = st.score()
                    before_tat = mean_tat(st)
                    before_cnt = st.cnt
                    for b in es:
                        st.remove(int(b))
                    tr = st.trial(k)
                    if tr is None:
                        for b in es:
                            restore_one(st, int(b))
                        continue
                    st.commit(k, tr)
                    inserted = [int(k)]
                    # Depth-2: reinsert each ejected task elsewhere, best
                    # exact-delta opportunity first.
                    for b in es:
                        bt = int(task_a[int(b)])
                        if st.done[bt]:
                            continue
                        best_alt = None
                        best_d = 1e-12
                        for alt in opps_by_task[bt]:
                            if int(alt) == int(b):
                                continue
                            tra = st.trial(int(alt))
                            if tra is None:
                                continue
                            d = exact_delta(st, int(alt), tra)
                            if d > best_d:
                                best_d = d
                                best_alt = int(alt)
                        if best_alt is not None:
                            tra = st.trial(best_alt)
                            if tra is not None:
                                st.commit(best_alt, tra)
                                inserted.append(best_alt)
                    if accept_ok(st, before_score, before_tat, before_cnt):
                        improved = True
                        break
                    # Roll back exactly; rebuild from snapshot if a
                    # restore unexpectedly fails.
                    for ins in reversed(inserted):
                        st.remove(ins)
                    ok = True
                    for b in es:
                        if not st.done[int(task_a[int(b)])]:
                            if not restore_one(st, int(b)):
                                ok = False
                    if not ok:
                        return build(before_sel), improved, True
                # end ejection sets
            # end opps
        return st, improved, False

    # ---- perturbed iterated ejection until the deadline --------------------
    # When a round finds no improving ejection, apply a deterministic
    # perturbation kick: remove a seeded-random set of low
    # weight-per-occupied-time scheduled tasks plus their temporal
    # neighbours on the same satellite, repair by regret-style insertion in
    # descending weight order (exact-delta + trial gap/battery checks and
    # the cumulative TAT budget), then run the next ejection round.  Kicks
    # always start from the best-ever plan, so a kicked plan that does not
    # improve within the following round is discarded (restart-from-best).
    kick_rng = random.Random(world_seed)
    kick_sizes = [6, 10, 14, 8, 12, 15, 5, 11, 9, 13, 7, 15]
    kick_idx = 0
    best_tat_sel = None
    best_tat_score = -1.0

    def eff_of(st, k):
        t = int(task_a[int(k)])
        gb = float(st.gap_before[int(k)])
        occ = float(end_a[int(k)] - start_a[int(k)]) + (gb if gb == gb and gb > 0 else float(nadir_a[int(k)]))
        return float(w_task[t]) / max(1.0, occ)

    def kick_and_repair(st):
        sel = st.selection()
        if not sel:
            return st
        size = kick_sizes[kick_idx % len(kick_sizes)]
        pool = sorted(sel, key=lambda x: eff_of(st, x))[:max(size, len(sel) // 4)]
        base = kick_rng.sample(pool, min(size, len(pool))) if pool else []
        victims = []
        seen_v = set()
        for k in base:
            k = int(k)
            if k not in seen_v:
                seen_v.add(k); victims.append(k)
            s = int(sat_a[k]); lst = st.timelines[s]
            try:
                pos = lst.index(k)
            except ValueError:
                continue
            for nb in (lst[pos - 1] if pos > 0 else None,
                       lst[pos + 1] if pos + 1 < len(lst) else None):
                if nb is not None and int(nb) not in seen_v:
                    seen_v.add(int(nb)); victims.append(int(nb))
        for k in victims:
            st.remove(int(k))
        # Regret-style repair: undone tasks in descending weight order, each
        # inserted at its best exact-delta feasible opportunity.
        undone = [t for t in range(n_tasks) if not st.done[t]]
        undone.sort(key=lambda t: (-float(w_task[t]),
                                   -float(w_task[t]) / max(1.0, float(tasks[t]['duration_s'])),
                                   float(tasks[t]['due_s'])))
        for t in undone:
            if time.time() > search_deadline:
                break
            if st.done[t]:
                continue
            best_alt = None; best_d = 1e-12
            for alt in opps_by_task[t]:
                tra = st.trial(int(alt))
                if tra is None:
                    continue
                d = exact_delta(st, int(alt), tra)
                if d > best_d:
                    best_d = d; best_alt = int(alt)
            if best_alt is not None:
                before_tat_k = mean_tat(st)
                tra = st.trial(best_alt)
                if tra is not None:
                    st.commit(best_alt, tra)
                    mt = mean_tat(st)
                    if mt > tat_cap + tat_allowance() and mt > before_tat_k - 1e-9:
                        st.remove(best_alt)
        return st

    rounds_no_best = 0
    while time.time() < search_deadline:
        state, improved, rebuilt = ejection_pass(state)
        cur_score = state.score(); cur_tat = mean_tat(state)
        if state.cnt >= cr_floor_cnt and cur_tat <= tat_cap and cur_score > best_tat_score + 1e-12:
            best_tat_score = cur_score; best_tat_sel = state.selection()
        if state.cnt >= cr_floor_cnt and cur_score > best_score + 1e-12:
            best_score = cur_score; best_sel = state.selection()
            rounds_no_best = 0
        else:
            rounds_no_best += 1
        if time.time() >= search_deadline:
            break
        # Perturbation kick from best-ever (also on improving rounds every
        # few rounds is unnecessary; kick only when progress stalls, plus
        # periodically to use the full deadline productively).
        if improved and rounds_no_best == 0 and kick_idx % 3 != 2:
            continue
        state = build(best_sel)
        state = kick_and_repair(state)
        kick_idx += 1
        if rounds_no_best >= 8:
            rounds_no_best = 0

    selection = [int(x) for x in best_sel]
    # Prefer a TAT-cap-feasible plan if it costs at most 0.20 score points.
    if best_tat_sel is not None and best_tat_score >= best_score - 0.20:
        selection = [int(x) for x in best_tat_sel]

    # ---- final exact validation with fallback --------------------------------
    def checked(sel):
        try:
            if time.time() > final_deadline:
                return False
            res = sim.check(world, [int(x) for x in sel])
            return bool(res.get('valid'))
        except Exception:
            return False

    if checked(selection):
        return selection
    if fallback_sel and checked(fallback_sel):
        return [int(x) for x in fallback_sel]
    # Last resort: chronological plan if it validates, else the best plan
    # found (empty list is always a syntactically valid return).
    return [int(x) for x in fallback_sel] if fallback_sel else []
