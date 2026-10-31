"""Paper-style Revisit metric on the 5 test missions: mean requirement-floored gap G (6.80 h = every target met) and mean
satellite count, from sealed evaluation outputs (work/sealed/revisit/<tag>_test/metrics.json).
Usage: python analysis/revisit_paper_metric.py p0 w2c10 ..."""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from paths import WORK
for tag in sys.argv[1:]:
    m = json.load(open(os.path.join(WORK, 'sealed', 'revisit', f'{tag}_test', 'metrics.json')))['per_case']; v = [r for r in m.values() if r.get('valid')]
    print(f"{tag}: valid {len(v)}/5  G = {sum(r['capped_mean_gap_h'] for r in v) / len(v):.3f} h  mean satellites = {sum(r['n_satellites'] for r in v) / len(v):.2f}"
          f"  missions with a missed target = {sum(r['n_targets_missing'] > 0 for r in v)}")
