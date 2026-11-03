"""Run Epoch Scientist on your own machine: Meta Muse Wonder inside AI-Scientist-v3 + OpenCode, CPU only.

  python runner/local/run_local.py --task revisit --check            # free: install + harness checks, no model calls
  MODEL_API_KEY=... python runner/local/run_local.py --task revisit  # full run (about 2 h, about $30 Meta-reported)
  python runner/local/run_local.py --task-dir tasks/my_problem --data-dir /path/to/dev_data --check   # your own problem

Steps (same as the runs in this repo): Node 22 + OpenCode 1.18.29 + headless-cli, the AI-Scientist-v3 fork with the Meta
provider patch, web tools off, task packages added to the pipeline venv, a harness-path gate that must reproduce the
program_0 score, a model ping and a 150 s bash-timeout gate, then `agsci run` with a budget guard.
Everything is installed under --work (default work/local). Your own ~/.config is not touched (XDG dirs point into --work).
The key is read from MODEL_API_KEY (or META_API_KEY) and never printed; it is redacted from the results."""
import os, sys, json, time, subprocess, threading, shutil, tarfile, glob, argparse, signal
from pathlib import Path

ROOT = Path(os.environ.get('MS_ROOT', Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(ROOT))
FORK = 'https://codeload.github.com/theainerd/AI-Scientist-v3/tar.gz/refs/heads/main'
HL_SHA = '93cd9b06b85f848af1308c41e018991b33907c5e'
PRESETS = {   # task folder, development missions only (held-out missions never reach the agent), expected program_0 score
    'revisit': ('tasks/revisit', 'revisit', [f'case_{i:04d}' for i in range(1, 5)], 69.820818),
    'aeossp': ('tasks/aeossp', 'aeossp', [f'case_{i:04d}' for i in range(1, 8)], 74.926186)}

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument('--task', choices=sorted(PRESETS), help='a problem shipped in this repo')
ap.add_argument('--task-dir', help='your own task folder (task.md, evaluate.py, program_0/, idea_example.json, rubrics_example.json)')
ap.add_argument('--data-dir', help='development data for --task-dir (exported to the evaluator as DATA_DIR)')
ap.add_argument('--name', help='example name inside the harness (default: task folder name)')
ap.add_argument('--expected-score', type=float, help='program_0 score the harness gate must reproduce (skip the comparison if omitted)')
ap.add_argument('--work', default=str(ROOT / 'work' / 'local'))
ap.add_argument('--model', default=os.environ.get('AISCI_MODEL', 'meta/muse-wonder-1.0'))
ap.add_argument('--cycles', type=int, default=int(os.environ.get('AISCI_CYCLES', '20')), help='idea cycles in total')
ap.add_argument('--workers', type=int, default=int(os.environ.get('AISCI_WORKERS', '2')))
ap.add_argument('--budget-usd', type=float, default=float(os.environ.get('AISCI_BUDGET_USD', '40')), help='stop when the Meta-reported cost reaches this minus $4')
ap.add_argument('--hours', type=float, default=11.0, help='wall-clock limit for the run')
ap.add_argument('--check', action='store_true', help='install and run the free checks only; no model calls')
A = ap.parse_args()
if not (A.task or A.task_dir): ap.error('give --task or --task-dir')

T0 = time.time(); WORK = Path(A.work).resolve(); OUTD = WORK / 'out'; TMP = WORK / 'tmp'
for p in (OUTD, TMP): p.mkdir(parents=True, exist_ok=True)
STATUS = {'mode': None, 'steps': [], 'model': A.model}
def log(*a): print(f'[{(time.time()-T0)/60:6.1f} min]', *a, flush=True)
def save_status(): (OUTD / 'status.json').write_text(json.dumps(STATUS, indent=1))
def sh(cmd, check=True, env=None, cwd=None, logfile=None):
    log('$', cmd if len(cmd) < 300 else cmd[:300] + ' ...')
    with (open(logfile, 'a') if logfile else open(os.devnull, 'w')) as lf:
        p = subprocess.Popen(cmd, shell=True, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        tail = []
        for line in p.stdout:
            lf.write(line); tail = (tail + [line.rstrip()])[-40:]
            if logfile is None or 'heartbeat' in line.lower() or 'phase' in line.lower(): print('   ', line.rstrip()[:300], flush=True)
        rc = p.wait()
    STATUS['steps'].append({'cmd': cmd[:200], 'rc': rc, 'min': round((time.time()-T0)/60, 1)}); save_status()
    if check and rc: print('\n'.join(tail)); raise SystemExit(f'FAILED rc={rc}: {cmd[:200]}')
    return rc, tail

# 1. task + development data
if A.task:
    tdir, NAME, dev, EXPECTED = PRESETS[A.task]; TASK = ROOT / tdir
    from paths import REVISIT_DATA, AEOSSP_PACK
    DATA = WORK / 'data' / NAME
    if not (DATA / 'cases' / 'train').exists():
        src = Path(REVISIT_DATA if NAME == 'revisit' else AEOSSP_PACK)
        if not (src / 'cases' / 'train').exists(): raise SystemExit(f'missing {src}: run `make fetch` first' + (' and `make pack-aeossp`' if NAME == 'aeossp' else ''))
        for c in dev:
            shutil.copytree(src / 'cases' / 'train' / c, DATA / 'cases' / 'train' / c, dirs_exist_ok=True)
            if (src / 'worlds').exists(): shutil.copytree(src / 'worlds' / 'train' / c, DATA / 'worlds' / 'train' / c, dirs_exist_ok=True)
else:
    TASK = Path(A.task_dir).resolve(); NAME = A.name or TASK.name; EXPECTED = None
    DATA = Path(A.data_dir).resolve() if A.data_dir else None
    for f in ('task.md', 'evaluate.py', 'program_0'):
        if not (TASK / f).exists(): raise SystemExit(f'{TASK} has no {f}')
if A.expected_score is not None: EXPECTED = A.expected_score
if (ROOT / '.env').exists():   # KEY=VALUE lines; values already in the environment win
    for ln in (ROOT / '.env').read_text().splitlines():
        if '=' in ln and not ln.lstrip().startswith('#'):
            k, v = ln.split('=', 1); k = k.strip(); v = v.strip().strip('"').strip("'")
            if k and v and k not in os.environ: os.environ[k] = v
key = (os.environ.get('MODEL_API_KEY') or os.environ.get('META_API_KEY') or '').strip() or None
STATUS['mode'] = 'CHECK' if (A.check or not key) else 'RUN'; STATUS['task'] = str(TASK); STATUS['data'] = str(DATA); save_status()
log('mode', STATUS['mode'], '| task', TASK, '| data', DATA)
if not key and not A.check: log('no MODEL_API_KEY set: running the free checks only')

# 2. toolchain, all under WORK (isolated from your own config)
env = dict(os.environ)
env.update({'XDG_CONFIG_HOME': str(WORK / 'xdg' / 'config'), 'XDG_DATA_HOME': str(WORK / 'xdg' / 'data'), 'XDG_CACHE_HOME': str(WORK / 'xdg' / 'cache'), 'XDG_STATE_HOME': str(WORK / 'xdg' / 'state'),
            'NPM_CONFIG_PREFIX': str(TMP / 'npm'), 'NPM_CONFIG_CACHE': str(WORK / 'cache' / 'npm'), 'UV_CACHE_DIR': str(WORK / 'cache' / 'uv'),
            'AGENTIC_TEMP_ROOT': str(TMP / 'agtmp')})
(TMP / 'agtmp').mkdir(exist_ok=True)
nv = subprocess.run('node -p "process.versions.node.split(\'.\')[0]"', shell=True, capture_output=True, text=True).stdout.strip() if shutil.which('node') else ''
if not nv.isdigit() or int(nv) < 22:
    sh(f'{sys.executable} -m pip install -q --target {TMP}/nodewheel nodejs-wheel-binaries==22.20.0', env=env)
    nw = Path(f'{TMP}/nodewheel/nodejs_wheel'); sb = TMP / 'nodebin'; sb.mkdir(exist_ok=True)   # the wheel's own npm/npx launchers break when copied; use shims
    for tool, js in (('node', None), ('npm', 'npm-cli.js'), ('npx', 'npx-cli.js')):
        f = sb / tool
        f.write_text(f'#!/bin/sh\nexec "{nw}/bin/node" "$@"\n' if js is None else f'#!/bin/sh\nexec "{nw}/bin/node" "{nw}/lib/node_modules/npm/bin/{js}" "$@"\n'); f.chmod(0o755)
    env['PATH'] = f'{sb}:' + env['PATH']; STATUS['node'] = 'nodejs-wheel-binaries 22.20.0'
sh(f'{sys.executable} -m pip install -q --target {TMP}/pytools uv', env=env)
env['PATH'] = f'{TMP}/npm/bin:{TMP}/pytools/bin:' + env['PATH']
sh('node --version && npm --version && git --version && uv --version', env=env)
sh('npm i -g opencode-ai@1.18.29 >/dev/null 2>&1 && opencode --version', env=env)
HL = TMP / 'headless'
if HL.exists(): shutil.rmtree(HL)
HL.mkdir()
sh(f'curl -sL https://codeload.github.com/RobertTLange/headless-cli/tar.gz/{HL_SHA} | tar xz --exclude=.githooks -C {HL} --strip-components=1', env=env)
sh(f'cd {HL} && npm install --no-audit --no-fund --ignore-scripts >/dev/null 2>&1 && npm run build >/dev/null 2>&1 && chmod +x dist/cli.js && node dist/cli.js --version', env=env)
env['HEADLESS_BIN'] = str(HL / 'dist/cli.js')

# 3. AI-Scientist-v3 fork + Meta provider patch + web tools off
REPO = TMP / 'AI-Scientist-v3-main'
if REPO.exists(): shutil.rmtree(REPO)
sh(f'curl -sL {FORK} | tar xz --exclude=.githooks -C {TMP}', env=env)
sh(f'cd {REPO} && (grep -q "selected_provider=\\"meta\\"" src/scripts/lib/container_agent.sh && echo "fork already patched") || patch -p1 < {ROOT}/runner/patches/meta_provider.patch', env=env)
cfg = Path(env['XDG_CONFIG_HOME']) / 'opencode'; cfg.mkdir(parents=True, exist_ok=True)
oc = json.load(open(REPO / 'configs/opencode/opencode.meta.json'))
oc.setdefault('tools', {}).update({'webfetch': False, 'websearch': False}); oc.setdefault('permission', {}).update({'webfetch': 'deny'})
(cfg / 'opencode.json').write_text(json.dumps(oc, indent=1)); env['OPENCODE_CONFIG'] = str(cfg / 'opencode.json'); STATUS['web_tools'] = 'disabled'
sh(f'cd {REPO} && git init -q && git add -A && git -c user.email=run@local -c user.name=run commit -qm base', check=False, env=env)
sh(f'cd {REPO} && uv sync -q', env=env)
EX = REPO / 'examples' / NAME
shutil.copytree(TASK, EX, dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'metrics.json', 'correct.json'))
if DATA: env['DATA_DIR'] = str(DATA); env[NAME.upper() + '_PACK'] = str(DATA)
AG = f'{REPO}/.venv/bin/agsci'
ARGS = (f'examples/{NAME} container.enabled=false agent.name=opencode agent.model={A.model} '
        f'investigation.execution.max_idea_cycles={A.cycles} investigation.execution.workers={A.workers} ablations.execution.num_replications=1 '
        'ablations.execution.max_evals_per_variant=2 logging.heartbeat_seconds=60 execution.phases=investigation')
if key: env['MODEL_API_KEY'] = key
env['OPENCODE_EXPERIMENTAL_BASH_DEFAULT_TIMEOUT_MS'] = '600000'   # evaluations take minutes; the 120 s default kills them
sh(f'cd {REPO} && {AG} doctor {ARGS}', check=False, env=env, logfile=OUTD / 'doctor.log')
sh(f'cd {REPO} && {AG} run {ARGS} --dry-run', check=False, env=env, logfile=OUTD / 'dryrun.log')
DRY_OK = all(s not in open(OUTD / 'dryrun.log').read() for s in ('Config error', 'Traceback'))
# The harness evaluates with the PIPELINE venv: add the task's requirements there, holding the pipeline's pins fixed.
req = TASK / 'requirements.txt'
if req.exists():
    sh(f"cd {REPO} && uv pip freeze --python .venv/bin/python | grep '==' > {TMP}/agsci_constraints.txt; "
       f"uv pip install -q --python .venv/bin/python -c {TMP}/agsci_constraints.txt -r {req}", check=False, env=env, logfile=OUTD / 'pkgs.log')

# 4. harness-path gate: score program_0 exactly as an attempt folder would (top-level task files only)
GATE = TMP / 'gate'
if GATE.exists(): shutil.rmtree(GATE)
GATE.mkdir(); shutil.copytree(EX / 'program_0', GATE / 'program_0', ignore=shutil.ignore_patterns('__pycache__', 'metrics.json', 'correct.json'))
(GATE / 'idea').mkdir()
for f in EX.iterdir():
    if f.is_file(): shutil.copy2(f, GATE / 'idea' / f.name)
sh(f'cd {REPO} && PYTHONPATH={REPO} .venv/bin/python -m src.investigation.evaluate_program --evaluator {GATE}/idea/evaluate.py '
   f'--program-dir {GATE}/program_0 --timeout-seconds 900', check=False, env=env, logfile=OUTD / 'baseline_eval.log')
GATE_SCORE = None
for f in [GATE / 'program_0/metrics.json'] + sorted(GATE.glob('**/metrics.json')):
    try: m = json.load(open(f)); GATE_SCORE = m.get('combined_score'); STATUS['gate_error'] = m.get('error'); break
    except Exception: pass
GATE_OK = isinstance(GATE_SCORE, (int, float)) and (EXPECTED is None or abs(GATE_SCORE - EXPECTED) < 0.05)
STATUS.update({'gate_score': GATE_SCORE, 'gate_expected': EXPECTED, 'gate_ok': GATE_OK, 'dry_run_ok': DRY_OK}); save_status()
log('HARNESS-PATH BASELINE', GATE_SCORE, 'expected', EXPECTED, 'OK' if GATE_OK else 'FAILED', '| dry run', 'OK' if DRY_OK else 'FAILED')
if STATUS['mode'] == 'CHECK':
    log('CHECK done: toolchain, patch, doctor, dry run and the program_0 gate ran with no model calls. Logs:', OUTD); raise SystemExit(0 if (GATE_OK and DRY_OK) else 1)
if not (GATE_OK and DRY_OK): log('checks failed, stopping before the paid run'); raise SystemExit(1)

# 5. model ping + 150 s bash-timeout gate (a few cents), then the run
ok_reply = lambda tl: any(t.strip().lower().strip('."') == 'ok' for t in tl[-6:])
rcE, tE = sh(f'cd {TMP} && $HEADLESS_BIN opencode --usage --allow yolo --model {A.model} --reasoning-effort high --prompt "Reply with the single word ok" 2>&1 | tail -8', check=False, env=env)
if rcE == 0 and ok_reply(tE): ARGS += ' agent.reasoning_effort=high'; STATUS['reasoning_effort'] = 'high'
rc2, t2 = sh(f'cd {TMP} && $HEADLESS_BIN opencode --usage --allow yolo --model {A.model} --prompt "Reply with the single word ok" 2>&1 | tail -8', check=False, env=env)
if rc2 != 0 or not ok_reply(t2): log('MODEL PING FAILED, stopping before the paid run:', t2[-3:]); raise SystemExit(1)
TG = TMP / 'tgate_ok'
if TG.exists(): TG.unlink()
sh(f'cd {TMP} && $HEADLESS_BIN opencode --usage --allow yolo --model {A.model} --prompt "Use the bash tool exactly once to run this command: '
   f'sleep 150 && touch {TG} . Do not pass a timeout parameter. After the tool returns, reply with the single word done." 2>&1 | tail -8', check=False, env=env)
if not TG.exists(): log('TIMEOUT GATE FAILED, stopping before the paid run'); raise SystemExit(1)
log('timeout gate OK')

stop = threading.Event(); PROC = {}
def snapshot():
    runs = sorted(glob.glob(f'{REPO}/results/{NAME}/*/[0-9]*')); snap = {'elapsed_min': round((time.time()-T0)/60, 1)}
    if not runs: return snap
    r = runs[-1]; scores = []
    for f in glob.glob(r + '/investigation/**/metrics.json', recursive=True):
        try:
            v = json.load(open(f)).get('combined_score')
            if isinstance(v, (int, float)): scores.append(float(v))
        except Exception: pass
    snap['attempts_scored'] = len(scores)
    if scores: snap['best_score'] = max(scores)
    for f in sorted(glob.glob(r + '/**/cost_summary.json', recursive=True))[-1:]:
        try: snap['cost_usd'] = float(json.load(open(f)).get('total_cost_usd', 0))
        except Exception: pass
    return snap
def heartbeat():
    while not stop.wait(120):
        snap = snapshot(); STATUS['heartbeat'] = snap; save_status()
        log('heartbeat · attempts scored', snap.get('attempts_scored', 0), '· best score', snap.get('best_score', '-'), '· Meta cost $%.2f' % snap.get('cost_usd', 0))
        if snap.get('cost_usd', 0) >= A.budget_usd - 4.0 and not STATUS.get('budget_stop'):
            STATUS['budget_stop'] = snap; save_status(); log('BUDGET GUARD: stopping the run')
            if PROC.get('p'): os.killpg(PROC['p'].pid, signal.SIGINT)
threading.Thread(target=heartbeat, daemon=True).start()
with open(OUTD / 'run.log', 'a') as lf:
    p = subprocess.Popen(f'cd {REPO} && {AG} run {ARGS}', shell=True, env=env, stdout=lf, stderr=subprocess.STDOUT, start_new_session=True); PROC['p'] = p
    try: rc = p.wait(timeout=A.hours * 3600)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGINT); time.sleep(300)
        if p.poll() is None: os.killpg(p.pid, signal.SIGKILL)
        rc = p.wait()
stop.set(); STATUS['run_rc'] = rc; STATUS['final'] = snapshot(); save_status()
res = REPO / 'results'
if res.exists():
    for f in res.rglob('*'):
        try:
            if f.is_file() and f.stat().st_size < 50_000_000 and key.encode() in f.read_bytes(): f.write_bytes(f.read_bytes().replace(key.encode(), b'[REDACTED]'))
        except Exception: pass
    with tarfile.open(OUTD / 'results.tar.gz', 'w:gz') as tf: tf.add(res, arcname='results', filter=lambda ti: None if 'node_modules' in ti.name else ti)
log('done', json.dumps(STATUS['final']), '| results:', OUTD / 'results.tar.gz')
