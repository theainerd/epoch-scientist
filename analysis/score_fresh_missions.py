"""Score the fresh-mission generalisation test exactly as pre-registered (results/revisit/fresh_missions/PREREG.md).
Expert (j2_rgt_set_cover) plans are scored with sim.mission_score on the official verifier output, the same rule as
analysis/score_revisit_yardstick.py; Muse and start scores come from tasks/revisit/evaluate.py (metrics.json).
Usage: python analysis/score_fresh_missions.py [DIR]   (default: results/revisit/fresh_missions; a rerun writes work/fresh_missions)"""
import os, sys, json, csv
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from paths import ROOT
sys.path.insert(0, os.path.join(ROOT, 'tasks', 'revisit')); import sim
D = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'results', 'revisit', 'fresh_missions')
CASES_DIR = os.path.join(ROOT, 'results', 'revisit', 'fresh_missions')     # mission files always come from the repo copy


def j2_row(ds, outb, c):
    vo = os.path.join(outb, c, 'verify.out')
    if not os.path.exists(vo) or os.path.getsize(vo) == 0: return None
    v = json.load(open(vo)); w = sim.build_world(os.path.join(ds, 'cases', 'test', c)); m = v['metrics']
    n = len(json.load(open(os.path.join(outb, c, 'solution.json')))['satellites'])
    g = [m['target_gap_summary'][t['id']]['max_revisit_gap_hours'] for t in w['targets']]
    return dict(valid=v['is_valid'], score=sim.mission_score(w, n, g, v['is_valid']), sats=n, missing=m['threshold_violation_count'],
                req_h=w['targets'][0]['expected_revisit_period_hours'], cap=w['cap'])


def prog(d, c):
    p = json.load(open(os.path.join(d, 'metrics.json')))['per_case'][c]
    return dict(valid=p['valid'], score=p['score'], sats=p.get('n_satellites'), missing=p.get('n_targets_missing'))


def table(ds, j2_dir, muse_dir, start_dir, cases):
    rows = []
    for c in cases:
        j = j2_row(ds, j2_dir, c)
        if j is None: continue
        m, s = prog(muse_dir, c), prog(start_dir, c)
        rows.append(dict(case=c, req_h=j['req_h'], cap=j['cap'],
                         start_valid=s['valid'], start_score=round(s['score'], 3), start_sats=s['sats'], start_missing=s['missing'],
                         muse_valid=m['valid'], muse_score=round(m['score'], 3), muse_sats=m['sats'], muse_missing=m['missing'],
                         j2_valid=j['valid'], j2_score=round(j['score'], 3), j2_sats=j['sats'], j2_missing=j['missing']))
    return rows


def write(rows, path):
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


cases = [f'case_{i:04d}' for i in range(1, 21)]
rows = table(CASES_DIR, os.path.join(D, 'j2'), os.path.join(D, 'muse'), os.path.join(D, 'start'), cases)
n = len(rows); mean = lambda k: round(sum(r[k] for r in rows) / n, 2)
print(f'fresh missions scored: {n}/20')
if n:
    write(rows, os.path.join(D, 'fresh_missions_results.csv'))
    print('1. Muse > expert on', sum(r['muse_score'] > r['j2_score'] for r in rows), 'of', n)
    print('2. mean score       start', mean('start_score'), '| Muse', mean('muse_score'), '| expert', mean('j2_score'))
    print('3. mean satellites  start', mean('start_sats'), '| Muse', mean('muse_sats'), '| expert', mean('j2_sats'))
    print('4. every target met start', sum(r['start_missing'] == 0 for r in rows), '| Muse', sum(r['muse_missing'] == 0 for r in rows),
          '| expert', sum(r['j2_missing'] == 0 for r in rows))
    print('5. valid plans      start', sum(bool(r['start_valid']) for r in rows), '| Muse', sum(bool(r['muse_valid']) for r in rows),
          '| expert', sum(bool(r['j2_valid']) for r in rows))
    print('Muse: fewer satellites AND no more missed targets than the expert on',
          sum(r['muse_sats'] < r['j2_sats'] and r['muse_missing'] <= r['j2_missing'] for r in rows), 'of', n)
cy = table(os.path.join(CASES_DIR, 'cyclone'), os.path.join(D, 'j2_cyclone'), os.path.join(D, 'muse_cyclone'),
           os.path.join(D, 'start_cyclone'), ['case_0001'])
if cy:
    write(cy, os.path.join(D, 'cyclone_results.csv')); r = cy[0]
    print(f"cyclone watch: start {r['start_score']} ({r['start_sats']} sats, {r['start_missing']} missed) | Muse {r['muse_score']} "
          f"({r['muse_sats']} sats, {r['muse_missing']} missed) | expert {r['j2_score']} ({r['j2_sats']} sats, {r['j2_missing']} missed)")
