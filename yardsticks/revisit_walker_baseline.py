"""Simple starting program: Walker-delta constellation at the satellite cap + time-ordered greedy photos."""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # sibling modules (revisit_sim, baseline)
import sys, json, math, time
import numpy as np, brahe
import revisit_sim as S

def walker(n, alt_m=700e3, inc=55.0, planes=None, F=1):
    planes = planes or max(1, int(round(math.sqrt(n))))
    while n % planes: planes -= 1
    per = n // planes
    return [S.kepler_state(alt_m, inc, 360.0 * p / planes, 360.0 * s / per + 360.0 * F * p / n) for p in range(planes) for s in range(per)]

def schedule(case, states):
    ts, eci, ecef, props = S.propagate(case, states); att = case['model']['attitude_model']
    dur = case['targets'][0]['min_duration_sec']; need = int(math.ceil(dur / S.STEP))      # samples checked: start, +10, +20
    actions, mids = [], {}
    for i in range(len(states)):
        vis = S.visible(case, ecef[i]); cands = []
        for j in range(vis.shape[0]):
            v = vis[j].astype(int); d = np.diff(np.r_[0, v, 0]); st = np.where(d == 1)[0]; en = np.where(d == -1)[0]
            for a, b in zip(st, en):
                if b - a >= need:
                    k = a + (b - a - need) // 2; s0 = ts[k]
                    if s0 + dur <= case['horizon_s']: cands.append((s0, j))
        cands.sort(); last = None
        for s0, j in cands:
            mid = s0 + dur / 2; ep = S.epoch(case['start']) + float(mid)
            sat = np.asarray(props[i].state_eci(ep), float)[:3]; tv = np.asarray(brahe.position_ecef_to_eci(ep, case['targets'][j]['ecef']), float) - sat
            if last is not None:
                lv, lend = last; c = float(tv @ lv / (np.linalg.norm(tv) * np.linalg.norm(lv)))
                if s0 - lend < S.slew_time(math.degrees(math.acos(max(-1, min(1, c)))), att) + att['settling_time_sec'] + 1e-6: continue
            actions.append((i, j, s0, s0 + dur)); mids.setdefault(j, []).append(mid); last = (tv, s0 + dur)
    return actions, mids

if __name__ == '__main__':
    case = S.load_case(sys.argv[1]); out = sys.argv[2]
    n = int(sys.argv[3]) if len(sys.argv) > 3 else case['cap']
    t0 = time.time(); st = walker(n); acts, mids = schedule(case, st); g = S.gaps(case, mids)
    req = np.array([t['expected_revisit_period_hours'] for t in case['targets']])
    S.write_solution(case, st, acts, out)
    print(json.dumps(dict(n=n, actions=len(acts), own_capped_gap=round(float(np.maximum(g, req).mean()), 3), own_violations=int((g > req + 1e-9).sum()), secs=round(time.time() - t0, 1))))
