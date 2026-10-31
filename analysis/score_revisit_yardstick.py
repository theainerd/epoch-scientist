"""Score the j2_rgt_set_cover solver runs (work/yardsticks/...) with the task's per-mission rule (sim.mission_score).
Writes results/revisit/yardstick_j2_solver.csv."""
import os, sys, json, csv, glob
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from paths import ROOT, WORK, REVISIT_DATA
sys.path.insert(0, os.path.join(ROOT, 'tasks', 'revisit')); import sim
B = os.path.join(WORK, 'yardsticks', 'revisit_constellation', 'j2_rgt_set_cover'); rows = []
for vo in sorted(glob.glob(os.path.join(B, '*', 'case_*', 'verify.out'))):
    d = os.path.dirname(vo); sp, c = d.split(os.sep)[-2:]; v = json.load(open(vo)); w = sim.build_world(os.path.join(REVISIT_DATA, 'cases', sp, c)); m = v['metrics']
    n = len(json.load(open(os.path.join(d, 'solution.json')))['satellites']); g = [m['target_gap_summary'][t['id']]['max_revisit_gap_hours'] for t in w['targets']]
    rows.append(dict(split=sp, case=c, role='dev' if sp == 'train' and c <= 'case_0004' else 'sealed', cap=w['cap'], req_h=w['targets'][0]['expected_revisit_period_hours'],
                     j2_valid=v['is_valid'], j2_sats=n, j2_missing=m['threshold_violation_count'], j2_score=round(sim.mission_score(w, n, g, v['is_valid']), 3)))
with open(os.path.join(ROOT, 'results', 'revisit', 'yardstick_j2_solver.csv'), 'w', newline='') as f:
    wr = csv.DictWriter(f, fieldnames=list(rows[0])); wr.writeheader(); wr.writerows(rows)
print(len(rows), 'missions scored')
