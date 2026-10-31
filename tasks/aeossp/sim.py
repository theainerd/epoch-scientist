"""Helper library for the satellite observation planning task (free to import from program.py).

A world is a plain dict (built by the evaluator) with:
  opportunity arrays, length n (one entry = one possible observation that already satisfies the task
  time window, exact duration, sensor type, line of sight and off-nadir limit):
    sat (int), task (int), start_s (int), end_s (int)       seconds from horizon start
    weight (float)                                           value of the task it completes
    look_start, look_end (n,3)                               unit pointing direction (inertial frame) at start / end
    nadir_slew_s (float)                                     slew+settle time needed from nadir pointing
  satellites: list of dicts (slew limits, settling time, battery/power model)
  tasks: list of dicts (id, weight, release_s, due_s, duration_s, sensor, lat_deg, lon_deg)
  sunlit: (n_sat, n_steps) bool, sunlit_step_s: sampling step of 'sunlit' in seconds
  horizon_s, action_time_step_s, energy_budget_wh

Rules checked by the official verifier (the final authority):
  1. each opportunity index at most once; actions are scored once per task (duplicates add nothing);
  2. on one satellite, actions must not overlap in time;
  3. between consecutive actions i -> j on one satellite: start_s[j] - end_s[i] >= required_gap_s(i, j);
     before the first action of a satellite: start_s[j] >= nadir_slew_s[j];
  4. battery never below 0 Wh (see battery model in check()).
"""
import math
import numpy as np

EPS = 1e-6


def slew_time_s(angle_deg, vmax_deg_s, amax_deg_s2):
    """Bang-coast-bang slew time for a rotation of angle_deg (verifier formula)."""
    a = max(0.0, float(angle_deg))
    if a <= EPS:
        return 0.0
    tri = vmax_deg_s * vmax_deg_s / amax_deg_s2
    if a <= tri:
        return 2.0 * math.sqrt(a / amax_deg_s2)
    return 2.0 * (vmax_deg_s / amax_deg_s2) + (a - tri) / vmax_deg_s


def angle_deg(u, v):
    c = float(np.dot(u, v)) / (float(np.linalg.norm(u)) * float(np.linalg.norm(v)))
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def required_gap_s(world, i, j):
    """Seconds needed between the end of opportunity i and the start of opportunity j (same satellite)."""
    s = world['satellites'][int(world['sat'][i])]
    ang = angle_deg(world['look_end'][i], world['look_start'][j])
    return slew_time_s(ang, s['max_slew_velocity_deg_per_s'], s['max_slew_acceleration_deg_per_s2']) + s['settling_time_s']


def check(world, selection):
    """Fast local check of a selection (list of opportunity indices).
    Returns dict(valid, issues, WCR, CR, TAT, PC, N). Mirrors the official verifier; the verifier is final
    (battery here uses the sunlit samples, so values may differ very slightly)."""
    sel = [int(k) for k in selection]
    issues = []
    n = len(world['sat'])
    if any(k < 0 or k >= n for k in sel):
        return dict(valid=False, issues=['index out of range'], N=0.0)
    if len(set(sel)) != len(sel):
        issues.append('duplicate opportunity index')
    H = float(world['horizon_s']); step = int(world['sunlit_step_s'])
    by_sat = {}
    for k in sel:
        by_sat.setdefault(int(world['sat'][k]), []).append(k)
    pc_total = 0.0
    for si, S in enumerate(world['satellites']):
        acts = sorted(by_sat.get(si, []), key=lambda k: (world['start_s'][k], world['end_s'][k]))
        windows = []
        accepted = []
        prev = None
        for k in acts:
            st, en = float(world['start_s'][k]), float(world['end_s'][k])
            if prev is None:
                need, have = float(world['nadir_slew_s'][k]), st
            else:
                if float(world['end_s'][prev]) > st:
                    issues.append(f'overlap on satellite {S["id"]}'); continue
                need, have = required_gap_s(world, prev, k), st - float(world['end_s'][prev])
            if have + EPS < need:
                issues.append(f'slew gap too short on satellite {S["id"]} before opportunity {k}'); continue
            if need > EPS:
                windows.append((st - need, st))
            accepted.append((st, en))
            prev = k
        ok_acts = sorted(accepted)
        windows.sort()
        pts = set(np.arange(0, H, step).tolist()) | {0.0, H}
        for a, b in ok_acts + windows:
            pts.add(a); pts.add(b)
        pts = np.array(sorted(p for p in pts if 0.0 <= p <= H))
        a, b = pts[:-1], pts[1:]; d = b - a; mid = a + d / 2

        def inside(iv):
            if not iv:
                return np.zeros(len(mid), bool)
            st = np.array([x for x, _ in iv]); en = np.array([y for _, y in iv])
            j = np.searchsorted(st, mid, side='right') - 1
            return (j >= 0) & (mid < en[np.clip(j, 0, None)])
        load = S['idle_power_w'] + S['imaging_power_w'] * inside(ok_acts) + S['slew_power_w'] * inside(windows)
        idx = np.minimum((mid // step).astype(int), world['sunlit'].shape[1] - 1)
        chg = np.where(world['sunlit'][si, idx], S['sunlit_charge_power_w'], 0.0)
        pc_total += float(np.sum(load * d)) / 3600.0
        delta = (chg - load) * d / 3600.0
        bat = S['initial_battery_wh']; cap = S['battery_capacity_wh']
        for q in range(len(delta)):
            bat += delta[q]
            if bat < -EPS:
                issues.append(f'battery below zero on satellite {S["id"]} near t={mid[q]:.0f}s'); break
            if bat > cap:
                bat = cap
    done = {}
    for k in sel:
        t = int(world['task'][k]); e = float(world['end_s'][k])
        done[t] = min(done.get(t, e), e)
    tasks = world['tasks']; W = sum(t['weight'] for t in tasks)
    wcr = sum(tasks[t]['weight'] for t in done) / W; cr = len(done) / len(tasks)
    tat = (sum(done[t] - tasks[t]['release_s'] for t in done) / len(done)) if done else None
    valid = not issues
    N = 0.0
    if valid and tat is not None:
        cl = lambda x: min(1.0, max(0.0, x))
        N = 100 * (0.45 * wcr + 0.20 * cr + 0.20 * cl(1 - tat / H) + 0.15 * cl(1 - pc_total / world['energy_budget_wh']))
    return dict(valid=valid, issues=issues[:20], n_issues=len(issues), WCR=wcr, CR=cr, TAT=tat, PC=pc_total, N=N)
