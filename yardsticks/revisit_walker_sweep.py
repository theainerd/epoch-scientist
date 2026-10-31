"""Headroom probe (no AI): plain sweep over Walker settings with fewer satellites. Own gap check (matches the verifier)."""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # sibling modules (revisit_sim, baseline)
import sys, json, itertools, time, numpy as np
import revisit_sim as S, baseline as B
case = S.load_case(sys.argv[1]); Ns = [int(x) for x in sys.argv[2].split(',')]
req = np.array([t['expected_revisit_period_hours'] for t in case['targets']])
for n in Ns:
    best = None; t0 = time.time()
    divs = [p for p in range(1, n + 1) if n % p == 0 and 2 <= p <= 8]
    for alt, inc, P in itertools.product([800e3, 850e3], [45.0, 52.0, 60.0], divs):
        for F in sorted({0, 1, max(0, P // 2)}):
            acts, mids = B.schedule(case, B.walker(n, alt, inc, P, F)); g = S.gaps(case, mids)
            v = int((g > req + 1e-9).sum()); cg = float(np.maximum(g, req).mean())
            if best is None or (v, cg) < (best['viol'], best['capped']): best = dict(n=n, alt=alt, inc=inc, P=P, F=F, viol=v, capped=round(cg, 3), max_gap=round(float(g.max()), 2))
            if v == 0: break
        if best['viol'] == 0: break
    best['secs'] = round(time.time() - t0); print(json.dumps(best), flush=True)
