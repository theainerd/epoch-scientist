"""Live proof on a brand-new mission (needs `make fetch`). Usage: python demo/live_proof.py [SEED] [--no-expert]
1. makes a new Revisit mission with the AstroAgentBench generator (a seed nobody has used),
2. plans it with the start program, with Muse's frozen program and (unless --no-expert) with the benchmark's expert solver,
3. checks every plan with the frozen official verifier and prints one comparison table.
Muse's program (results/revisit/programs/best_w2_cycle10.py) was written by Meta Muse Wonder on 30 Oct 2026; it is not changed."""
import os, sys, json, time, shutil, subprocess, yaml
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from paths import ROOT, AAB, WORK
sys.path.insert(0, os.path.join(ROOT, 'tasks', 'revisit')); import sim
SEED = int(next((a for a in sys.argv[1:] if a.isdigit()), 20261103)); EXPERT = '--no-expert' not in sys.argv
O = os.path.join(WORK, f'live_proof_{SEED}'); shutil.rmtree(O, ignore_errors=True); os.makedirs(O)
B, D, G = '\033[1m', '\033[2m', '\033[0m'
def say(*a): print(*a, flush=True)
_R = os.path.abspath(ROOT) + os.sep
def clean(x): return x.replace(sys.executable, 'python').replace(_R, '').replace(os.path.abspath(AAB), '$AAB')
def rel(p): return clean(os.path.abspath(p) if os.path.exists(p) else p)
def stream(cmd, cwd=None, env=None, log=None, beat=0, label=''):
    """Run cmd, print it, stream its output (dim, indented); every `beat` s print elapsed time."""
    say(f'      {D}$ ' + ' '.join(rel(c) for c in cmd)[:150] + G)
    t0 = time.time(); fh = open(log, 'w') if log else None
    p = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    import threading
    done = threading.Event()
    def hb():
        while not done.wait(beat):
            m, sec = divmod(int(time.time() - t0), 60); say(f'      {D}... {label} still running · {m}:{sec:02d} elapsed{G}')
    if beat: threading.Thread(target=hb, daemon=True).start()
    for line in p.stdout:
        if fh: fh.write(line)
        line = line.rstrip()
        if line.strip(): say(f'      {D}| {clean(line)[:140]}{G}')
    p.wait(); done.set()
    if fh: fh.close()
    if p.returncode: raise SystemExit(f'command failed ({p.returncode}): {cmd[:3]}')
    return time.time() - t0
def step(n, text): say(f'\n{B}[{n}/4] {text}{G}')
say(f'{B}EPOCH SCIENTIST · LIVE PROOF ON A BRAND-NEW MISSION{G}')
say(f"{D}Muse's program was written by Meta Muse Wonder (meta/muse-wonder-1.0) on 30 Oct 2026 and runs here unchanged.{G}")

step(1, f'Generate a new mission with the AstroAgentBench generator (seed {SEED})')
cfg = yaml.safe_load(open(os.path.join(ROOT, 'results', 'revisit', 'fresh_missions', 'splits_fresh.yaml')))
cfg['splits']['test'].update(seed=SEED, case_count=1, target_selection_seed_offset=SEED % 997)
cfg['splits']['train'].update(seed=SEED + 1, case_count=1)
yaml.safe_dump(cfg, open(os.path.join(O, 'splits.yaml'), 'w'), sort_keys=False)
t0 = time.time()
stream([sys.executable, '-m', 'benchmarks.revisit_constellation.generator.run', os.path.join(O, 'splits.yaml'),
        '--output-dir', os.path.join(O, 'mission'), '--download-dir', os.path.join(O, 'src')], cwd=AAB, env=dict(os.environ, PYTHONPATH=AAB))
case = os.path.join(O, 'mission', 'cases', 'test', 'case_0001'); w = sim.build_world(case); nT = len(w['targets'])
req = w['targets'][0]['expected_revisit_period_hours']
say(f'      {nT} places · each photographed at least every {req:g} h · 48 h · at most {w["cap"]} satellites   '
    f'{D}({time.time() - t0:.0f} s){G}')
say(f'      {D}first places: ' + ', '.join(t.get('name', t['id']) for t in json.load(open(os.path.join(case, 'mission.json')))['targets'][:4]) + f' ...{G}')

def program(label, path):
    out = os.path.join(O, label)
    stream([sys.executable, os.path.join(ROOT, 'tasks', 'revisit', 'evaluate.py'), '--program_path', path, '--results_dir', out,
            '--split', 'test', '--cases', 'case_0001'], env=dict(os.environ, DATA_DIR=os.path.join(O, 'mission')), beat=10, label={'start': 'start program', 'muse': "Muse's program"}[label])
    p = json.load(open(os.path.join(out, 'metrics.json')))['per_case']['case_0001']
    return dict(sats=p['n_satellites'], on_time=nT - p['n_targets_missing'], score=p['score'], valid=p['valid'], secs=p['solve_s'])
def show(r):
    say(f"      {r['sats']} satellites · {r['on_time']}/{nT} places on time · score {r['score']:.1f} · "
        f"{'valid' if r['valid'] else 'INVALID'} (official verifier) · planned in {r['secs']:.0f} s")
os.makedirs(os.path.join(O, 'mission', 'cases', 'train'), exist_ok=True)
step(2, 'Start program (satellites spread evenly, the program Muse started from)'); s = program('start', os.path.join(ROOT, 'tasks', 'revisit', 'program_0', 'src', 'program.py')); show(s)
step(3, "Muse's program (written by Meta Muse Wonder, frozen)"); m = program('muse', os.path.join(ROOT, 'results', 'revisit', 'programs', 'best_w2_cycle10.py')); show(m)
rows = [('Start program', s), ('Muse (Meta Muse Wonder)', m)]
if EXPERT:
    step(4, 'Expert solver j2_rgt_set_cover (the benchmark\'s own reference, hand-written by experts)')
    say(f'      {D}takes about 8-18 min on a laptop{G}')
    out = os.path.join(O, 'expert'); os.makedirs(out); t0 = time.time()
    stream(['bash', 'solvers/revisit_constellation/j2_rgt_set_cover/solve.sh', case, '', out], cwd=AAB, log=os.path.join(out, 'solve.log'), beat=20, label='expert solver',
           env=dict(os.environ, PYTHONPATH=os.path.join(ROOT, 'yardsticks', 'shim'), SOLVER_PYTHON=sys.executable))
    if not os.path.exists(os.path.join(out, 'solution.json')):
        raise SystemExit('expert solver produced no plan; see ' + os.path.join(out, 'solve.log'))
    say(f'      {D}$ python -m benchmarks.revisit_constellation.verifier.run <mission> expert/solution.json   (official verifier){G}')
    vr = subprocess.run([sys.executable, '-m', 'benchmarks.revisit_constellation.verifier.run', case, os.path.join(out, 'solution.json')],
                        cwd=AAB, env=dict(os.environ, PYTHONPATH=AAB), capture_output=True, text=True)
    v = json.loads(vr.stdout); mt = v['metrics']; n = len(json.load(open(os.path.join(out, 'solution.json')))['satellites'])
    g = [mt['target_gap_summary'][t['id']]['max_revisit_gap_hours'] for t in w['targets']]
    st = json.load(open(os.path.join(out, 'status.json')))['timing_seconds']['total']
    say(f"      {D}| is_valid={v['is_valid']} · threshold_violation_count={mt['threshold_violation_count']} · worst gap {max(g):.3f} h{G}")
    e = dict(sats=n, on_time=nT - mt['threshold_violation_count'], score=sim.mission_score(w, n, g, v['is_valid']), valid=v['is_valid'], secs=st)
    show(e); rows.append(('Expert solver (j2)', e))
else:
    step(4, 'Expert solver skipped (--no-expert)')
say(f'\n{B}RESULT on this brand-new mission (seed {SEED}){G}')
say(f"  {'':26s}{'satellites':>11s}{'on time':>10s}{'score':>8s}{'planned in':>12s}")
for name, r in rows:
    say(f"  {name:26s}{r['sats']:>11d}{str(r['on_time']) + '/' + str(nT):>10s}{r['score']:>8.1f}{r['secs']:>10.0f} s")
json.dump({k: v for k, v in rows}, open(os.path.join(O, 'result.json'), 'w'), indent=1)
