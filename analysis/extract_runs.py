"""Rebuild results/evo_runs.json from AI-Scientist-v3 run outputs: one record per attempt with worker, cycle, Muse's idea
title and hypothesis, dev score, kept flag, validity, and the parent program (found by matching program SHA-256s).
Usage: python analysis/extract_runs.py aeossp=<investigation dir> revisit=<investigation dir>
(investigation dir = <run>/results/<problem>/opencode/<timestamp>/investigation, from the Kaggle output results.tar.gz)"""
import os, sys, json, glob, hashlib
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from paths import ROOT
h = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()[:10] if os.path.exists(p) else None
out = {}
for arg in sys.argv[1:]:
    name, R = arg.split('=', 1); p0 = h(os.path.join(ROOT, 'tasks', name, 'program_0', 'src', 'program.py')); rows = []
    for a in (json.loads(l) for l in open(os.path.join(R, 'attempts_history.jsonl')) if l.strip()):
        d = os.path.join(R, f"worker_0{a['parallel_worker_index']}", 'ideas', a['idea_dir_name']); idea, pc = {}, {}
        try: idea = json.load(open(os.path.join(d, 'active_idea.json')))
        except Exception: pass
        try: pc = json.load(open(os.path.join(d, 'program_1', 'metrics.json'))).get('per_case', {})
        except Exception: pass
        m = a['metrics'] if isinstance(a['metrics'], dict) else eval(a['metrics'] or '{}')
        rows.append(dict(worker=a['parallel_worker_index'], cycle=a['parallel_worker_cycle_index'], t=a['timestamp'], title=idea.get('title', a['idea_dir_name']),
                         hyp=(idea.get('hypothesis') or '')[:700], score=m.get('combined_score'), correct=m.get('correct'), best_updated=a['best_updated'],
                         parent=h(os.path.join(d, 'program_0/src/program.py')), child=h(os.path.join(d, 'program_1/src/program.py')),
                         n_valid=sum(1 for r in pc.values() if r.get('valid')), n_cases=len(pc)))
    child = {r['child']: f"w{r['worker']}c{r['cycle']}" for r in rows}
    for r in rows: r['parent_of'] = 'start' if r['parent'] == p0 else child.get(r['parent'], '?')
    out[name] = sorted(rows, key=lambda r: r['t']); print(name, len(rows), 'attempts')
json.dump(out, open(os.path.join(ROOT, 'results', 'evo_runs.json'), 'w'), indent=1)
