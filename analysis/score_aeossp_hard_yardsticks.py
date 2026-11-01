"""Score the benchmark solvers (MWIS, greedy_lns) on the 5 hard AEOSSP missions and compare with the start program and Muse.
Run the solvers first:  for c in 1 2 3 4 5; do for s in mwis_conflict_graph greedy_lns; do
                          bash yardsticks/run_solver.sh aeossp_standard $s test_hard case_000$c; done; done   (~6-11 min each)
Usage: python analysis/score_aeossp_hard_yardsticks.py  -> results/aeossp/hard_missions_yardsticks.csv"""
import os, sys, json
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'yardsticks'))
from paths import ROOT, AAB, WORK
from aeossp_nscore import nscore
CASES = os.path.join(AAB, 'benchmarks', 'aeossp_standard', 'dataset', 'cases', 'test_hard')
m = pd.read_csv(os.path.join(ROOT, 'results', 'aeossp', 'sealed_per_mission.csv')); m = m[m.set == 'test_hard'].set_index('case')
rows = []
for c in [f'case_000{i}' for i in range(1, 6)]:
    row = dict(case=c, start_N=round(m.loc[c, 'base_N'], 3), start_valid=bool(m.loc[c, 'base_valid']),
               muse_N=round(m.loc[c, 'muse_N'], 3), muse_valid=bool(m.loc[c, 'muse_valid']))
    for solver, tag in [('mwis_conflict_graph', 'mwis'), ('greedy_lns', 'greedy_lns')]:
        d = json.load(open(os.path.join(WORK, 'yardsticks', 'aeossp_standard', solver, 'test_hard', c, 'verify.out')))
        row[f'{tag}_N'] = round(nscore(d['metrics'], os.path.join(CASES, c), d['valid']), 3); row[f'{tag}_valid'] = d['valid']
    rows.append(row)
df = pd.DataFrame(rows); out = os.path.join(ROOT, 'results', 'aeossp', 'hard_missions_yardsticks.csv'); df.to_csv(out, index=False)
print(df.to_string()); print('means:', df[['start_N', 'muse_N', 'mwis_N', 'greedy_lns_N']].mean().round(2).to_dict()); print('->', out)
