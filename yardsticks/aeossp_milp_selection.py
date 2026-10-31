"""Hidden yardstick: max-weight conflict-free selection (task once, no overlap, pairwise slew gaps) by MILP (HiGHS).
Built from the world pack. Writes the selection and scores it with the official verifier."""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import ROOT, AAB, WORK, ASSETS, FFMPEG, AEOSSP_PACK, REVISIT_DATA  # noqa: E402,F401
import sys, json, time, numpy as np
sys.path.insert(0, _os.path.join(ROOT, 'tasks', 'aeossp'))
import evaluate as ev, sim
from scipy.optimize import milp, LinearConstraint, Bounds
from scipy.sparse import coo_matrix
P = AEOSSP_PACK; import tempfile; _os.makedirs(_os.path.join(WORK, 'aeossp', 'milp'), exist_ok=True)
split, case, tl = sys.argv[1], sys.argv[2], float(sys.argv[3])
w = ev.load_world(P, split, case); n = len(w['sat']); t0 = time.time()
rows, cols = [], []
for k in range(n): rows.append(int(w['task'][k])); cols.append(k)
r = len(w['tasks']); npair = 0
for s in range(len(w['satellites'])):
    S = w['satellites'][s]; idx = np.flatnonzero(w['sat'] == s); idx = idx[np.argsort(w['start_s'][idx], kind='stable')]
    st, en = w['start_s'][idx], w['end_s'][idx]
    gmax = sim.slew_time_s(180.0, S['max_slew_velocity_deg_per_s'], S['max_slew_acceleration_deg_per_s2']) + S['settling_time_s']
    LS, LE = w['look_start'][idx], w['look_end'][idx]
    for a in range(len(idx)):
        hi = np.searchsorted(st, en[a] + gmax, side='right')
        if hi <= a + 1: continue
        bs = np.arange(a + 1, hi)
        ang = np.degrees(np.arccos(np.clip(LS[bs] @ LE[a], -1, 1)))
        vm, am = S['max_slew_velocity_deg_per_s'], S['max_slew_acceleration_deg_per_s2']; tri = vm * vm / am
        slew = np.where(ang <= tri, 2 * np.sqrt(np.maximum(ang, 0) / am), 2 * vm / am + (ang - tri) / vm)
        slew = np.where(ang <= 1e-6, 0.0, slew) + S['settling_time_s']
        conf = (en[a] > st[bs]) | ((st[bs] - en[a]) + 1e-6 < slew)
        for b in bs[conf]:
            rows += [r, r]; cols += [int(idx[a]), int(idx[b])]; r += 1; npair += 1
        # also forbid b starting before a's end when b starts earlier but overlaps: covered by symmetric scan (b>a by start)
A = coo_matrix((np.ones(len(rows)), (rows, cols)), shape=(r, n)).tocsr(); tb = time.time() - t0
W = sum(t['weight'] for t in w['tasks'])
c = -w['weight']
res = milp(c, constraints=LinearConstraint(A, -np.inf, 1), bounds=Bounds(0, 1), integrality=np.ones(n), options={'time_limit': tl, 'disp': False})
sel = np.flatnonzero(res.x > 0.5).tolist() if res.x is not None else []
sc = ev.score_case(P, split, case, sel, tempfile.gettempdir())
out = dict(case=f'{split}/{case}', n=n, pairs=npair, build_s=round(tb, 1), milp_s=round(time.time() - t0 - tb, 1), status=res.message[:40],
           WCR_opt=round(-res.fun / W, 4) if res.x is not None else None, dual=round(-res.mip_dual_bound / W, 4), **{k: (round(v, 4) if isinstance(v, float) else v) for k, v in sc.items() if k in ('valid', 'N', 'WCR', 'CR', 'TAT', 'PC_Wh')})
np.save(_os.path.join(WORK, 'aeossp', 'milp', f'{split}_{case}_milp_sel.npy'), np.array(sel)); print(json.dumps(out), flush=True)
