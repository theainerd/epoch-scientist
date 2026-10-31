PATCH = r'''diff -ruN fa/configs/opencode/README.md fb/configs/opencode/README.md
--- fa/configs/opencode/README.md	1970-01-01 05:30:00
+++ fb/configs/opencode/README.md	2026-10-27 12:12:23
@@ -0,0 +1,7 @@
+# Meta Model API with OpenCode
+
+1. Copy `opencode.meta.json` to `~/.config/opencode/opencode.json`.
+2. Export `MODEL_API_KEY` (never commit it).
+3. Run with `agent.name=opencode agent.model=meta/muse-spark-1.3` (or `meta/muse-wonder-1.0`).
+
+The `*meta*|*muse*` model hint in `src/scripts/lib/container_agent.sh` forwards only `MODEL_API_KEY` into containers.
diff -ruN fa/configs/opencode/opencode.meta.json fb/configs/opencode/opencode.meta.json
--- fa/configs/opencode/opencode.meta.json	1970-01-01 05:30:00
+++ fb/configs/opencode/opencode.meta.json	2026-10-27 12:12:23
@@ -0,0 +1,21 @@
+{
+  "$schema": "https://opencode.ai/config.json",
+  "provider": {
+    "meta": {
+      "npm": "@ai-sdk/openai",
+      "name": "Meta Model API",
+      "options": {
+        "baseURL": "https://api.meta.ai/v1",
+        "apiKey": "{env:MODEL_API_KEY}"
+      },
+      "models": {
+        "muse-spark-1.3": {
+          "name": "Muse Spark 1.3"
+        },
+        "muse-wonder-1.0": {
+          "name": "Muse Wonder 1.0"
+        }
+      }
+    }
+  }
+}
\ No newline at end of file
diff -ruN fa/src/investigation/script_runners.py fb/src/investigation/script_runners.py
--- fa/src/investigation/script_runners.py	2026-10-27 12:12:20
+++ fb/src/investigation/script_runners.py	2026-10-27 13:43:05
@@ -1170,12 +1170,20 @@
     if agent == "gemini" and reasoning_effort:
         raise ValueError("reasoning_effort is not supported for gemini")
     cmd = ["env", "HEADLESS_MODELS_DEV_CACHE="]
-    cmd.extend(
-        [
+    headless_bin = os.environ.get("HEADLESS_BIN", "").strip()
+    headless_cmd = (
+        [headless_bin]
+        if headless_bin
+        else [
             "npx",
             "-y",
             "git+https://github.com/RobertTLange/headless-cli.git#"
             "93cd9b06b85f848af1308c41e018991b33907c5e",
+        ]
+    )
+    cmd.extend(
+        [
+            *headless_cmd,
             agent,
             "--debug",
             "--usage",
diff -ruN fa/src/scripts/lib/container_agent.sh fb/src/scripts/lib/container_agent.sh
--- fa/src/scripts/lib/container_agent.sh	2026-10-27 12:12:20
+++ fb/src/scripts/lib/container_agent.sh	2026-10-27 12:12:23
@@ -219,6 +219,7 @@
           *anthropic*|*claude*) selected_provider="anthropic" ;;
           *google*|*gemini*) selected_provider="google" ;;
           *moonshot*) selected_provider="moonshot" ;;
+          *meta*|*muse*) selected_provider="meta" ;;
           *openai*|*gpt-*) selected_provider="openai" ;;
         esac
         [ -z "$selected_provider" ] || break
@@ -233,6 +234,7 @@
         anthropic) allowed_keys+=" ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN" ;;
         google) allowed_keys+=" GEMINI_API_KEY GOOGLE_API_KEY" ;;
         moonshot) allowed_keys+=" MOONSHOT_API_KEY" ;;
+        meta) allowed_keys+=" MODEL_API_KEY" ;;
         bedrock)
           allowed_keys+=" AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_BEARER_TOKEN_BEDROCK AWS_REGION AWS_DEFAULT_REGION AWS_REGION_NAME"
           ;;
diff -ruN fa/src/scripts/variant_agent.sh fb/src/scripts/variant_agent.sh
--- fa/src/scripts/variant_agent.sh	2026-10-27 12:12:20
+++ fb/src/scripts/variant_agent.sh	2026-10-27 12:12:23
@@ -38,7 +38,7 @@
 CONTAINER_NETWORK="bridge"
 CONTAINER_AUTH_ROOT="$HOME"
 CONTAINER_ENV_FILE=""
-VARIANT_AGENT_ALLOWED_ENV_KEYS="ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_BEARER_TOKEN_BEDROCK AWS_REGION AWS_DEFAULT_REGION AWS_REGION_NAME CLAUDE_CODE_OAUTH_TOKEN CLAUDE_CODE_USE_BEDROCK CURSOR_API_KEY DEEPSEEK_API_KEY GEMINI_API_KEY GOOGLE_API_KEY MOONSHOT_API_KEY OPENAI_API_KEY OPENROUTER_API_KEY PI_CODING_AGENT_PROVIDER PI_CODING_AGENT_MODEL PI_CODING_AGENT_MODELS S2_API_KEY"
+VARIANT_AGENT_ALLOWED_ENV_KEYS="ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_BEARER_TOKEN_BEDROCK AWS_REGION AWS_DEFAULT_REGION AWS_REGION_NAME CLAUDE_CODE_OAUTH_TOKEN CLAUDE_CODE_USE_BEDROCK CURSOR_API_KEY DEEPSEEK_API_KEY GEMINI_API_KEY GOOGLE_API_KEY MODEL_API_KEY MOONSHOT_API_KEY OPENAI_API_KEY OPENROUTER_API_KEY PI_CODING_AGENT_PROVIDER PI_CODING_AGENT_MODEL PI_CODING_AGENT_MODELS S2_API_KEY"
 POSTHOC_ENV_POLICY=0
 
 while [[ $# -gt 0 ]]; do
'''
"""AI-Scientist-v3 Revisit-constellation blind-discovery run on Kaggle (native mode, OpenCode + Meta Model API).
PREFLIGHT mode (no secret attached): install + agsci doctor + dry run, no model calls.
SMOKE mode (secret MODEL_API_KEY or META_API_KEY attached): circpack end to end, reduced budgets."""
import os, sys, json, time, subprocess, threading, shutil, tarfile, glob
from pathlib import Path
T0 = time.time(); OUTD = Path('/kaggle/working'); TMP = Path('/kaggle/tmp'); TMP.mkdir(exist_ok=True)
FORK = 'https://codeload.github.com/theainerd/AI-Scientist-v3/tar.gz/refs/heads/main'
MODEL = os.environ.get('AISCI_MODEL', 'meta/muse-wonder-1.0'); CYCLES = int(os.environ.get('AISCI_CYCLES', '20')); WORKERS = int(os.environ.get('AISCI_WORKERS', '2')); WALL_LIMIT_S = 11 * 3600
STATUS = {'mode': None, 'steps': [], 'model': MODEL}
def log(*a): print(f'[{(time.time()-T0)/60:6.1f} min]', *a, flush=True)
def save_status(): (OUTD / 'status.json').write_text(json.dumps(STATUS, indent=1))
def sh(cmd, check=True, env=None, cwd=None, logfile=None, timeout=None):
    log('$', cmd if len(cmd) < 300 else cmd[:300] + ' ...')
    with (open(logfile, 'a') if logfile else open(os.devnull, 'w')) as lf:
        p = subprocess.Popen(cmd, shell=True, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        tail = []
        for line in p.stdout:
            lf.write(line); tail = (tail + [line.rstrip()])[-40:]
            if logfile is None or 'heartbeat' in line.lower() or 'phase' in line.lower(): print('   ', line.rstrip()[:300], flush=True)
        rc = p.wait(timeout=timeout)
    STATUS['steps'].append({'cmd': cmd[:200], 'rc': rc, 'min': round((time.time()-T0)/60, 1)}); save_status()
    if check and rc: print('\n'.join(tail)); raise SystemExit(f'FAILED rc={rc}: {cmd[:200]}')
    return rc, tail

# 1. key (never printed)
key = None
try:
    from kaggle_secrets import UserSecretsClient
    for label in ('MODEL_API_KEY', 'META_API_KEY'):
        try: key = UserSecretsClient().get_secret(label).strip(); STATUS['secret_label'] = label; STATUS['key_len'] = len(key); break
        except Exception: pass
except Exception: pass
STATUS['mode'] = 'SMOKE' if key else 'PREFLIGHT'; save_status(); log('mode', STATUS['mode'])

# 2. toolchain
env = dict(os.environ); NODE = TMP / 'node'
if shutil.which('node') is None or int(subprocess.run('node -p "process.versions.node.split(\'.\')[0]"', shell=True, capture_output=True, text=True).stdout.strip() or 0) < 22:
    NODE.mkdir(parents=True, exist_ok=True); TXZ = TMP / 'node.tar.xz'
    rcN, _ = sh(f'curl -fL --retry 5 --retry-all-errors --retry-delay 10 --connect-timeout 30 --max-time 600 -o {TXZ} '
                f'https://nodejs.org/dist/v22.11.0/node-v22.11.0-linux-x64.tar.xz && xz -t {TXZ} && tar xJf {TXZ} -C {NODE} --strip-components=1', check=False)
    if rcN == 0 and (NODE / 'bin/node').exists():
        env['PATH'] = f'{NODE}/bin:' + env['PATH']; STATUS['node_source'] = 'nodejs.org'
    else:                                             # fallback: official Node 22 binary packaged on PyPI
        log('nodejs.org download failed, using the PyPI nodejs-wheel-binaries fallback')
        sh(f'pip install -q --target {TMP}/nodewheel nodejs-wheel-binaries==22.20.0')
        nb = next(Path(f'{TMP}/nodewheel').rglob('bin/node'))
        env['PATH'] = f'{nb.parent}:' + env['PATH']; STATUS['node_source'] = 'pypi nodejs-wheel-binaries 22.20.0'
    save_status()
env['NPM_CONFIG_PREFIX'] = str(TMP / 'npm'); env['PATH'] = f'{TMP}/npm/bin:' + env['PATH']
sh('node --version && npm --version && git --version', env=env)
sh('npm i -g opencode-ai@1.18.29 >/dev/null 2>&1 && opencode --version', env=env)
HL = TMP / 'headless'; HL_SHA = '93cd9b06b85f848af1308c41e018991b33907c5e'
if HL.exists(): shutil.rmtree(HL)
HL.mkdir()
sh(f'curl -sL https://codeload.github.com/RobertTLange/headless-cli/tar.gz/{HL_SHA} | tar xz -C {HL} --strip-components=1', env=env)
sh(f'cd {HL} && npm install --no-audit --no-fund --ignore-scripts >/dev/null 2>&1 && npm run build >/dev/null 2>&1 && chmod +x dist/cli.js && node dist/cli.js --version', env=env)
env['HEADLESS_BIN'] = str(HL / 'dist/cli.js')
sh('pip install -q uv && uv --version', env=env)
if False: sh('(command -v pdflatex && command -v bibtex) || (apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq '
   'texlive-latex-base texlive-latex-extra texlive-latex-recommended texlive-fonts-recommended texlive-bibtex-extra >/dev/null)', check=False, env=env)

# 3. fork + Meta provider patch
REPO = TMP / 'AI-Scientist-v3-main'
if REPO.exists(): shutil.rmtree(REPO)
sh(f'curl -sL {FORK} | tar xz -C {TMP}')
(TMP / 'meta_provider.patch').write_text(PATCH)
sh(f'cd {REPO} && (grep -q "selected_provider=\\"meta\\"" src/scripts/lib/container_agent.sh && echo "fork already patched") || patch -p1 < {TMP}/meta_provider.patch')
cfg = Path.home() / '.config/opencode'; cfg.mkdir(parents=True, exist_ok=True)
_oc = json.load(open(REPO / 'configs/opencode/opencode.meta.json'))
_oc.setdefault('tools', {}).update({'webfetch': False, 'websearch': False})
_oc.setdefault('permission', {}).update({'webfetch': 'deny'})
(cfg / 'opencode.json').write_text(json.dumps(_oc, indent=1)); STATUS['web_tools'] = 'disabled'
sh(f'cd {REPO} && git init -q && git add -A && git -c user.email=run@local -c user.name=run commit -qm base', check=False)
sh(f'cd {REPO} && uv sync -q', env=env)
TASKSRC = [p for p in glob.glob('/kaggle/input/**/task_revisit/task.md', recursive=True)]
assert TASKSRC, 'revisit task dataset not attached'
shutil.copytree(os.path.dirname(TASKSRC[0]), REPO / 'examples/revisit', dirs_exist_ok=True)
PACK = [os.path.dirname(os.path.dirname(p)) for p in glob.glob('/kaggle/input/**/pack/cases/train', recursive=True)]
assert PACK, 'revisit mission pack not found in the dataset'
env['REVISIT_PACK'] = PACK[0]; env['DATA_DIR'] = PACK[0]; STATUS['pack'] = PACK[0]; STATUS['task_src'] = TASKSRC[0]
AG = f'{REPO}/.venv/bin/agsci'
WHEELS = (glob.glob('/kaggle/input/**/wheels', recursive=True) or ['/tmp'])[0]; STATUS['wheels'] = WHEELS
env['AGENTIC_TEMP_ROOT'] = str(TMP / 'agtmp'); (TMP / 'agtmp').mkdir(exist_ok=True)
ARGS = (f'examples/revisit container.enabled=false agent.name=opencode agent.model={MODEL} '
        f'investigation.execution.max_idea_cycles={CYCLES} investigation.execution.workers={WORKERS} ablations.execution.num_replications=1 '
        'ablations.execution.max_evals_per_variant=2 logging.heartbeat_seconds=60 '
        'execution.phases=investigation')
if key: env['MODEL_API_KEY'] = key
# Run 2 lost 14/20 attempts: OpenCode's bash tool kills commands after 120 s by default (opencode 1.18.29:
# DEFAULT_TIMEOUT_MS=120000, MAX_TIMEOUT_MS=600000) and evaluate.py needs 130-400 s on Kaggle. Raise the default to the maximum.
env['OPENCODE_EXPERIMENTAL_BASH_DEFAULT_TIMEOUT_MS'] = '600000'; STATUS['bash_timeout_ms'] = 600000
# Budget guard: Meta has no hard spend cap. Stop the run when the harness-reported cost reaches BUDGET_USD - BUDGET_MARGIN_USD
# (the margin covers the 2 agent sessions in flight, whose cost is reported only when they end).
BUDGET_USD = float(os.environ.get('AISCI_BUDGET_USD', '40')); BUDGET_MARGIN_USD = 4.0
STATUS['budget_usd'] = BUDGET_USD
sh(f'cd {REPO} && {AG} doctor {ARGS}', check=False, env=env, logfile=OUTD / 'doctor.log')
print(open(OUTD / 'doctor.log').read()[-4000:])
sh(f'cd {REPO} && {AG} run {ARGS} --dry-run', check=False, env=env, logfile=OUTD / 'dryrun.log')
print(open(OUTD / 'dryrun.log').read()[-3000:])

# The harness evaluates with the PIPELINE venv (WRAPPER_PYTHON = sys.executable), not a task venv: add the task packages there,
# holding the pipeline's own pinned versions fixed.
sh(f"cd {REPO} && uv pip freeze --python .venv/bin/python | grep '==' > {TMP}/agsci_constraints.txt; "
   f"uv pip install -q --python .venv/bin/python -c {TMP}/agsci_constraints.txt --find-links {WHEELS} scipy brahe==1.8.0 && "
   f".venv/bin/python -c 'import scipy, brahe, numpy; print(\"PKGS OK brahe\", brahe.__version__, \"scipy\", scipy.__version__, \"numpy\", numpy.__version__)'",
   check=False, env=env, logfile=OUTD / 'pkgs.log')
print(open(OUTD / 'pkgs.log').read()[-800:])
# Exact harness path: src.investigation.evaluate_program strips the environment like a real attempt.
EXPECTED_P0 = float(os.environ.get('AISCI_EXPECTED_P0', '69.820818'))
GATE = TMP / 'gate'
if GATE.exists(): shutil.rmtree(GATE)
GATE.mkdir(); shutil.copytree(REPO / 'examples/revisit/program_0', GATE / 'program_0', ignore=shutil.ignore_patterns('__pycache__', 'metrics.json', 'correct.json'))
# Score program_0 from a copy that holds ONLY the task's top-level files, as each attempt folder does
# (run 1 of this task lost its attempts because the frozen verifier sat in a subfolder).
(GATE / 'idea').mkdir()
for _f in (REPO / 'examples/revisit').iterdir():
    if _f.is_file(): shutil.copy2(_f, GATE / 'idea' / _f.name)
STATUS['gate_files'] = sorted(p.name for p in (GATE / 'idea').iterdir()); save_status()
sh(f'cd {REPO} && PYTHONPATH={REPO} .venv/bin/python -m src.investigation.evaluate_program --evaluator {GATE}/idea/evaluate.py --program-dir {GATE}/program_0 --timeout-seconds 900',
   check=False, env=env, logfile=OUTD / 'baseline_eval.log')
GATE_SCORE = None
for f in [GATE / 'program_0/metrics.json'] + sorted(GATE.glob('**/metrics.json')):
    try: m = json.load(open(f)); GATE_SCORE = m.get('combined_score'); STATUS['gate_error'] = m.get('error'); break
    except Exception: pass
GATE_OK = isinstance(GATE_SCORE, (int, float)) and abs(GATE_SCORE - EXPECTED_P0) < 0.05
STATUS['gate_score'] = GATE_SCORE; STATUS['gate_ok'] = GATE_OK; save_status()
log('HARNESS-PATH BASELINE', GATE_SCORE, 'OK' if GATE_OK else 'FAILED', STATUS.get('gate_error'))
print(open(OUTD / 'baseline_eval.log').read()[-1500:])
# 4. provider check + full run
sh(f'cd {TMP} && $HEADLESS_BIN opencode --model {MODEL} --prompt hi --print-command 2>&1 | tail -3', check=False, env=env)
DRY_OK = 'Config error' not in open(OUTD / 'dryrun.log').read() and 'Traceback' not in open(OUTD / 'dryrun.log').read()
STATUS['dry_run_ok'] = DRY_OK; save_status(); log('dry run ok', DRY_OK)
if key and not GATE_OK:
    log('HARNESS-PATH BASELINE FAILED, stopping before the paid run'); STATUS['stopped'] = 'harness baseline failed'; save_status(); raise SystemExit(0)
if key and DRY_OK:
    rc, tail = sh(f'cd {TMP} && opencode run --model {MODEL} "Reply with the single word ok" 2>&1 | tail -5', check=False, env=env)
    ok_reply = lambda tl: any(t.strip().lower().strip('.\"') == 'ok' for t in tl[-6:])
    rcE, tailE = sh(f'cd {TMP} && $HEADLESS_BIN opencode --usage --allow yolo --model {MODEL} --reasoning-effort high --prompt "Reply with the single word ok" 2>&1 | tail -8', check=False, env=env)
    STATUS['effort_ping'] = {'rc': rcE, 'tail': tailE[-4:]}
    if rcE == 0 and ok_reply(tailE):
        ARGS += ' agent.reasoning_effort=high'; STATUS['reasoning_effort'] = 'high'; log('reasoning effort high accepted')
    else:
        STATUS['reasoning_effort'] = 'default'; log('reasoning effort flag not accepted, using the default effort')
    save_status()
    rc2, tail2 = sh(f'cd {TMP} && $HEADLESS_BIN opencode --usage --allow yolo --model {MODEL} --prompt "Reply with the single word ok" 2>&1 | tail -8', check=False, env=env)
    STATUS['headless_ping'] = {'rc': rc2, 'tail': tail2[-6:]}; save_status()
    if rc2 != 0 or not any(t.strip().lower().strip('."') == 'ok' for t in tail2[-6:]):
        log('MODEL PING FAILED, stopping before the paid run:', tail2[-3:]); STATUS['stopped'] = 'model ping failed'; save_status(); raise SystemExit(0)
    STATUS['opencode_ping'] = tail[-3:]; save_status()
    # Timeout gate (costs about $0.05): the agent's bash tool must survive a 150 s command with its DEFAULT timeout.
    TG = TMP / 'tgate_ok'
    if TG.exists(): TG.unlink()
    rcT, tailT = sh(f'cd {TMP} && $HEADLESS_BIN opencode --usage --allow yolo --model {MODEL} --prompt '
                    f'"Use the bash tool exactly once to run this command: sleep 150 && touch {TG} . Do not pass a timeout parameter. '
                    f'After the tool returns, reply with the single word done." 2>&1 | tail -8', check=False, env=env)
    STATUS['timeout_gate'] = {'rc': rcT, 'ok': TG.exists(), 'tail': tailT[-4:]}; save_status()
    if not TG.exists():
        log('TIMEOUT GATE FAILED (agent bash tool still stops a 150 s command), stopping before the paid run:', tailT[-3:])
        STATUS['stopped'] = 'timeout gate failed'; save_status(); raise SystemExit(0)
    log('timeout gate OK: a 150 s agent command completed')
    stop = threading.Event()
    wb = None
    try:
        from kaggle_secrets import UserSecretsClient
        for _lab in ('WANDB_API_KEY', 'WANDB', 'wandb', 'WANDB_KEY', 'wandb_api_key', 'W&B'):
            try: os.environ['WANDB_API_KEY'] = UserSecretsClient().get_secret(_lab).strip(); STATUS['wandb_label'] = _lab; break
            except Exception: pass
        if 'WANDB_API_KEY' not in os.environ: raise RuntimeError('no W&B secret attached')
        import wandb
        wb = wandb.init(project='aisci-revisit', name='revisit-blind-' + MODEL.split('/')[-1] + '-' + time.strftime('%m%d-%H%M'), config={'model': MODEL, 'task': 'revisit_blind', 'cycles': CYCLES, 'workers': WORKERS})
        STATUS['wandb_url'] = wb.url; save_status(); log('W&B dashboard:', wb.url)
    except Exception as e:
        log('W&B off:', type(e).__name__)
    def snapshot():
        runs = sorted(glob.glob(f'{REPO}/results/revisit/*/[0-9]*'))
        r = runs[-1] if runs else None; snap = {'elapsed_min': round((time.time()-T0)/60, 1)}
        if r:
            scores = []
            for f in glob.glob(r + '/investigation/**/metrics.json', recursive=True):
                try:
                    v = json.load(open(f)).get('combined_score')
                    if isinstance(v, (int, float)): scores.append((os.path.getmtime(f), float(v)))
                except Exception: pass
            scores.sort(); snap['attempts_scored'] = len(scores)
            if scores: snap['best_score'] = max(v for _, v in scores); snap['last_score'] = scores[-1][1]
            best = None
            for f in glob.glob(r + '/investigation/**/metrics.json', recursive=True):
                try:
                    mm = json.load(open(f))
                    if isinstance(mm.get('combined_score'), (int, float)) and (best is None or mm['combined_score'] > best['combined_score']): best = mm
                except Exception: pass
            if best:
                for k in ('n_valid', 'n_cases_all_targets_met', 'total_satellites', 'max_solve_s', 'eval_seconds'):
                    if isinstance(best.get(k), (int, float)): snap['best/' + k] = best[k]
            # Count every finished attempt (one history row per cycle); unscored = no numeric score > -100.
            try:
                hist = [json.loads(l) for l in open(r + '/investigation/attempts_history.jsonl') if l.strip()]
                def _sc(h):
                    m = h.get('metrics') if isinstance(h.get('metrics'), dict) else {}
                    v = m.get('combined_score'); return v if isinstance(v, (int, float)) and v > -100 else None
                snap['attempts_total'] = len(hist); snap['attempts_unscored'] = sum(_sc(h) is None for h in hist)
            except Exception: pass
            errs = []
            for f in glob.glob(r + '/investigation/**/ideas/*/program_*/metrics.json', recursive=True):
                try:
                    e = json.load(open(f)).get('error')
                    if e: errs.append((os.path.getmtime(f), str(e)[:300]))
                except Exception: pass
            snap['attempts_failed'] = len(errs)
            if errs: STATUS['last_error'] = sorted(errs)[-1][1]
            for f in sorted(glob.glob(r + '/**/cost_summary.json', recursive=True))[-1:]:
                try:
                    for k, v in json.load(open(f)).items():
                        try: snap['cost/' + k] = float(v)
                        except Exception: pass
                except Exception: pass
        return snap
    BEAT = [0]
    def heartbeat():
        while not stop.wait(120):
            snap = snapshot(); STATUS['heartbeat'] = snap; save_status(); log('heartbeat', json.dumps(snap)[:400])
            BEAT[0] += 1
            spent = snap.get('cost/total_cost_usd', 0.0)
            if spent >= BUDGET_USD - BUDGET_MARGIN_USD and not STATUS.get('budget_stop'):
                STATUS['budget_stop'] = {'spent_usd': spent, 'at_min': snap['elapsed_min']}; STATUS['stopped'] = 'budget guard'; save_status()
                log(f'BUDGET GUARD: reported cost ${spent:.2f} >= ${BUDGET_USD - BUDGET_MARGIN_USD:.2f}; stopping agsci (SIGINT, then SIGKILL after 300 s)')
                subprocess.run(['pkill', '-INT', '-f', f'{AG} run'], check=False)
                def _hard_stop():
                    time.sleep(300)
                    for pat in (f'{AG} run', 'opencode'): subprocess.run(['pkill', '-KILL', '-f', pat], check=False)
                threading.Thread(target=_hard_stop, daemon=True).start()
            if BEAT[0] % 5 == 0 and (REPO / 'results').exists():
                # FIFOs (.agent_stream_*.fifo) and files that vanish mid-copy made run 2's copytree raise; skip them and log a count.
                try: shutil.copytree(REPO / 'results', OUTD / 'results_partial', dirs_exist_ok=True, ignore_dangling_symlinks=True,
                                     ignore=shutil.ignore_patterns('*.npz', '*.fifo', '.agentic_history*', '.evaluation_runtime'))
                except shutil.Error as e: log('partial backup: skipped', len(e.args[0]) if e.args else '?', 'files')
                except Exception as e: log('partial backup failed', type(e).__name__)
            if wb:
                wb.log(snap)
                if STATUS.get('last_error'): wb.summary['last_error'] = STATUS['last_error']
            if STATUS.get('last_error'): log('last attempt error:', STATUS['last_error'][:200])
    threading.Thread(target=heartbeat, daemon=True).start()
    rc, _ = sh(f'cd {REPO} && timeout -s INT -k 300 {int(WALL_LIMIT_S)} {AG} run {ARGS}', check=False, env=env, logfile=OUTD / 'run.log')
    stop.set(); STATUS['run_rc'] = rc
    final = snapshot(); STATUS['final'] = final
    if wb: wb.log(final); wb.summary.update(final); wb.finish()
    # token use from OpenCode session storage (counts only)
    tok = {'input': 0, 'output': 0, 'reasoning': 0, 'cache_read': 0, 'messages': 0}
    for f in glob.glob(str(Path.home() / '.local/share/opencode/storage/message/**/*.json'), recursive=True):
        try:
            m = json.load(open(f)); t = m.get('tokens') or {}
            tok['input'] += t.get('input', 0) or 0; tok['output'] += t.get('output', 0) or 0
            tok['reasoning'] += t.get('reasoning', 0) or 0; tok['cache_read'] += (t.get('cache') or {}).get('read', 0) or 0
            tok['messages'] += 1
        except Exception: pass
    STATUS['tokens'] = tok; save_status(); log('tokens', tok)
    res = REPO / 'results'
    def _redact(root):
        n = 0
        for f in Path(root).rglob('*'):
            try:
                if f.is_file() and f.stat().st_size < 50_000_000:
                    b = f.read_bytes()
                    if key.encode() in b: f.write_bytes(b.replace(key.encode(), b'[REDACTED]')); n += 1
            except Exception: pass
        return n
    STATUS['files_redacted'] = _redact(res) if res.exists() else 0
    if (OUTD / 'results_partial').exists(): STATUS['files_redacted'] += _redact(OUTD / 'results_partial')
    save_status()
    if res.exists():
        with tarfile.open(OUTD / 'results.tar.gz', 'w:gz') as tf: tf.add(res, arcname='results')
    pass
STATUS['total_min'] = round((time.time()-T0)/60, 1); save_status(); log('done', json.dumps(STATUS)[:1500])
