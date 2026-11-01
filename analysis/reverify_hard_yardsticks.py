"""Re-check the MWIS and greedy_lns plans on the 5 hard AEOSSP missions with the official verifier, without rerunning the
solvers. Plans: results/aeossp/hard_yardsticks_raw/<solver>/<case>/solution.json.gz (made by yardsticks/run_solver.sh).
Checks: (1) the verifier gives the same validity and metrics as the stored verify_summary.json, (2) the N score matches
results/aeossp/hard_missions_yardsticks.csv.   Usage: python analysis/reverify_hard_yardsticks.py   (needs `make fetch`)"""
import os, sys, json, gzip, subprocess, tempfile
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'yardsticks'))
from paths import ROOT, AAB
from aeossp_nscore import nscore
RAW = os.path.join(ROOT, 'results', 'aeossp', 'hard_yardsticks_raw')
CASES = os.path.join(AAB, 'benchmarks', 'aeossp_standard', 'dataset', 'cases', 'test_hard')
table = pd.read_csv(os.path.join(ROOT, 'results', 'aeossp', 'hard_missions_yardsticks.csv')).set_index('case')
env = dict(os.environ, PYTHONPATH=AAB)
ok = True
for solver, tag in [('mwis_conflict_graph', 'mwis'), ('greedy_lns', 'greedy_lns')]:
    for c in [f'case_000{i}' for i in range(1, 6)]:
        d = os.path.join(RAW, solver, c)
        with tempfile.TemporaryDirectory() as tmp:
            sol = os.path.join(tmp, 'solution.json')
            open(sol, 'wb').write(gzip.open(os.path.join(d, 'solution.json.gz')).read())
            out = subprocess.run([sys.executable, '-m', 'benchmarks.aeossp_standard.verifier.run',
                                  f'benchmarks/aeossp_standard/dataset/cases/test_hard/{c}', sol],
                                 cwd=AAB, env=env, capture_output=True, text=True, check=True).stdout
        v = json.loads(out); ref = json.load(open(os.path.join(d, 'verify_summary.json')))
        same = v['valid'] == ref['valid'] and all(abs(v['metrics'][k] - ref['metrics'][k]) < 1e-9 for k in ref['metrics'])
        n = round(nscore(v['metrics'], os.path.join(CASES, c), v['valid']), 3)
        match = abs(n - table.loc[c, f'{tag}_N']) < 1e-6 and bool(v['valid']) == bool(table.loc[c, f'{tag}_valid'])
        ok &= same and match
        print(f'{solver:20s} {c}  valid={v["valid"]}  N={n:.3f}  same_as_stored={same}  matches_table={match}')
print('ALL MATCH' if ok else 'MISMATCH'); sys.exit(0 if ok else 1)
