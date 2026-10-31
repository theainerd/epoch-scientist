"""Evaluator: satellite observation planning (7 development cases, official verifier).

Program contract (program.py):  solve(world, time_limit_s) -> list of opportunity indices.
Each case runs in a fresh process with 1 CPU thread and a wall-clock limit of TIME_LIMIT_S seconds.
The selection is converted to observation actions and scored by the frozen official verifier.
Case score N = 100*(0.45*WCR + 0.20*CR + 0.20*[1-TAT/H] + 0.15*[1-PC/E_budget]); invalid or late case = 0.
combined_score = mean N over the development cases (higher is better).
"""
import os, sys, json, time, glob, argparse, traceback, importlib.util, hashlib
import multiprocessing as mp
from datetime import datetime, timedelta, timezone
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from capture import OutputCapture

TIME_LIMIT_S = 60.0
GRACE_S = 15.0
DEV_CASES = [f'case_{i:04d}' for i in range(1, 8)]
N_PARALLEL = max(1, min(4, (os.cpu_count() or 2)))
THREAD_VARS = ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS')
EXPECTED_SHA256 = {'capture.py': 'cc7a660d33180d61479bbf0df59fae815d0119dd19d9e5290e0d2126096804d5', 'sim.py': '1bdcea353a1afb08cddbb6b5bf37233e360861f78fa5f490a9a4bdbda40ffdc7', 'aab_verifier.py': '7fa4005905cdf1b7cdb0d83633dc3a6f2336c1bc0b9f4830b8657b78609d37e7'}   # capture.py, sim.py and the frozen verifier


def check_integrity():
    for f, h in EXPECTED_SHA256.items():
        if hashlib.sha256(open(os.path.join(HERE, f), 'rb').read()).hexdigest() != h:
            raise RuntimeError(f'integrity check failed: {f} was modified')


def find_pack():
    for v in ('AEOSSP_PACK', 'DATA_DIR', 'AGENTIC_DATA_DIR'):
        p = os.environ.get(v)
        if p and os.path.isdir(os.path.join(p, 'worlds')): return p
    for c in glob.glob('/kaggle/input/**/worlds/train', recursive=True):
        return os.path.dirname(os.path.dirname(c))
    if os.path.isdir(os.path.join(HERE, 'data', 'worlds')): return os.path.join(HERE, 'data')
    raise FileNotFoundError('data pack not found: set DATA_DIR to the folder that holds worlds/ and cases/')


def load_world(pack, split, case):
    import numpy as np
    d = os.path.join(pack, 'worlds', split, case)
    z = np.load(os.path.join(d, 'world.npz')); meta = json.load(open(os.path.join(d, 'world.json')))
    w = {k: z[k].copy() for k in z.files}
    w['sunlit_step_s'] = int(w['sunlit_step_s'])
    w['weight'] = np.array([meta['tasks'][t]['weight'] for t in w['task']], float)
    w.update(satellites=meta['satellites'], tasks=meta['tasks'], horizon_s=meta['horizon_s'],
             action_time_step_s=meta['action_time_step_s'], case=meta['case'],
             energy_budget_wh=float(sum(s['battery_capacity_wh'] for s in meta['satellites'])))
    return w


def _child(program_path, pack, split, case, out_npy, err_json):
    for v in THREAD_VARS: os.environ[v] = '1'
    for v in ('AEOSSP_PACK', 'DATA_DIR', 'AGENTIC_DATA_DIR'): os.environ.pop(v, None)
    try:
        world = load_world(pack, split, case)
        sys.path.insert(0, os.path.dirname(os.path.abspath(program_path))); sys.path.insert(0, HERE)
        spec = importlib.util.spec_from_file_location('program', program_path); mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        t0 = time.time(); sel = mod.solve(world, TIME_LIMIT_S); dt = time.time() - t0
        import numpy as np
        np.save(out_npy, np.asarray(list(sel), dtype=np.int64))
        json.dump({'ok': True, 'solve_s': round(dt, 2)}, open(err_json, 'w'))
    except BaseException as e:
        json.dump({'ok': False, 'error': f'{type(e).__name__}: {e}'[:1500], 'trace': traceback.format_exc()[-3000:]}, open(err_json, 'w'))


def score_case(pack, split, case, sel, work):
    import numpy as np, yaml
    from aab_verifier import verify_solution
    w = load_world(pack, split, case); n = len(w['sat'])
    sel = [int(k) for k in sel]
    if any(k < 0 or k >= n for k in sel): return {'valid': False, 'N': 0.0, 'error': 'opportunity index out of range'}
    cd = os.path.join(pack, 'cases', split, case)
    m = yaml.safe_load(open(os.path.join(cd, 'mission.yaml')))['mission']
    hs = datetime.fromisoformat(m['horizon_start'].replace('Z', '+00:00')).astimezone(timezone.utc)
    iso = lambda s: (hs + timedelta(seconds=int(s))).strftime('%Y-%m-%dT%H:%M:%SZ')
    sat_ids = [s['id'] for s in w['satellites']]; task_ids = [t['id'] for t in w['tasks']]
    acts = [{'type': 'observation', 'satellite_id': sat_ids[w['sat'][k]], 'task_id': task_ids[w['task'][k]],
             'start_time': iso(w['start_s'][k]), 'end_time': iso(w['end_s'][k])} for k in sorted(sel, key=lambda k: (w['start_s'][k], w['sat'][k]))]
    sp = os.path.join(work, f'{case}_solution.json'); json.dump({'actions': acts}, open(sp, 'w'))
    r = verify_solution(cd, sp); mt = r.metrics
    H = float(w['horizon_s']); E = w['energy_budget_wh']; cl = lambda x: min(1.0, max(0.0, x))
    N = 0.0
    if r.valid and mt.get('TAT') is not None:
        N = 100 * (0.45 * mt['WCR'] + 0.20 * mt['CR'] + 0.20 * cl(1 - mt['TAT'] / H) + 0.15 * cl(1 - mt['PC'] / E))
    return {'valid': bool(r.valid), 'N': N, 'WCR': mt.get('WCR'), 'CR': mt.get('CR'), 'TAT': mt.get('TAT'), 'PC_Wh': mt.get('PC'),
            'n_actions': len(acts), 'n_violations': len(r.violations), 'violations': list(r.violations)[:5]}


def run_case(args):
    program_path, pack, split, case, work = args
    ctx = mp.get_context('spawn')
    out_npy = os.path.join(work, f'{case}_sel.npy'); err_json = os.path.join(work, f'{case}_status.json')
    t0 = time.time()
    p = ctx.Process(target=_child, args=(program_path, pack, split, case, out_npy, err_json)); p.start()
    p.join(TIME_LIMIT_S + GRACE_S)
    wall = time.time() - t0
    if p.is_alive():
        p.kill(); p.join(5)
        return case, {'valid': False, 'N': 0.0, 'error': f'time limit exceeded ({TIME_LIMIT_S:.0f} s)', 'wall_s': round(wall, 1)}
    if not os.path.isfile(err_json):
        return case, {'valid': False, 'N': 0.0, 'error': f'program process died (exit code {p.exitcode})', 'wall_s': round(wall, 1)}
    st = json.load(open(err_json))
    if not st.get('ok'):
        return case, {'valid': False, 'N': 0.0, 'error': st.get('error'), 'trace': st.get('trace', '')[-1500:], 'wall_s': round(wall, 1)}
    if st['solve_s'] > TIME_LIMIT_S:
        return case, {'valid': False, 'N': 0.0, 'error': f"solve() took {st['solve_s']} s > {TIME_LIMIT_S:.0f} s", 'wall_s': round(wall, 1)}
    import numpy as np
    res = score_case(pack, split, case, np.load(out_npy).tolist(), work)
    res['solve_s'] = st['solve_s']; res['wall_s'] = round(wall, 1)
    return case, res


def evaluate(program_path, pack, split, cases, work):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(N_PARALLEL) as ex:
        out = dict(ex.map(run_case, [(os.path.abspath(program_path), pack, split, c, work) for c in cases]))
    return {c: out[c] for c in cases}


def main(program_path, results_dir, verbose=True, split='train', cases=None):
    os.makedirs(results_dir, exist_ok=True); metrics = {}; correct = False; msg = None
    with OutputCapture(results_dir, tee=verbose):
        try:
            check_integrity(); pack = find_pack(); t0 = time.time()
            work = os.path.join(results_dir, '_cases'); os.makedirs(work, exist_ok=True)
            per = evaluate(program_path, pack, split, cases or DEV_CASES, work)
            Ns = [per[c]['N'] for c in per]
            metrics = {'combined_score': sum(Ns) / len(Ns), 'mean_N': sum(Ns) / len(Ns), 'n_valid': sum(per[c]['valid'] for c in per), 'n_cases': len(per)}
            for k in ('WCR', 'CR', 'TAT', 'PC_Wh'):
                v = [per[c][k] for c in per if per[c].get('valid') and per[c].get(k) is not None]
                metrics['mean_' + k] = (sum(v) / len(v)) if v else None
            metrics['max_solve_s'] = max((per[c].get('solve_s') or 0) for c in per)
            metrics['per_case'] = per; metrics['eval_seconds'] = round(time.time() - t0, 1)
            correct = metrics['n_valid'] == metrics['n_cases']; msg = 'ok' if correct else 'some cases invalid or failed (scored 0)'
            print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in metrics.items() if k != 'per_case'}, indent=1))
            for c, r in per.items():
                print(c, {k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items() if k not in ('trace',)})
        except Exception as e:
            msg = f'{type(e).__name__}: {e}'[:2000]; print('[ERROR]', msg, file=sys.stderr); metrics = {'combined_score': -100.0, 'error': msg}
        json.dump(metrics, open(os.path.join(results_dir, 'metrics.json'), 'w'), indent=2, default=str)
        json.dump({'correct': correct, 'message': msg}, open(os.path.join(results_dir, 'correct.json'), 'w'), indent=2)
    return metrics


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--program_path', required=True); ap.add_argument('--results_dir', required=True)
    ap.add_argument('--verbose', action='store_true', default=True); ap.add_argument('--quiet', action='store_true')
    ap.add_argument('--split', default='train'); ap.add_argument('--cases', default=None, help='comma-separated (offline use only)')
    a = ap.parse_args(); main(a.program_path, a.results_dir, verbose=not a.quiet, split=a.split, cases=a.cases.split(',') if a.cases else None)
