"""Evaluator: constellation design for target revisit (4 development missions, frozen official verifier).

Program contract (program.py):  solve(world, time_limit_s) -> {'satellites': [ECI state 6-vectors at mission start],
                                                                 'actions': [(sat_index, target_index, start_s, end_s), ...]}
Each mission runs in a fresh process with 1 CPU thread and a wall-clock limit of TIME_LIMIT_S seconds.
The plan is written as solution.json and checked by the frozen official verifier (revisit_verifier.py) in a separate process.
Mission score (sim.mission_score): invalid or late = 0; if any target misses its revisit period: 70 * mean_j phi(gap_j);
if every target meets it: 70 + 30 * (cap - n_satellites) / (cap - 1).   combined_score = mean over the missions (higher is better).
"""
import os, sys, json, time, glob, argparse, traceback, importlib.util, hashlib
import multiprocessing as mp
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from capture import OutputCapture

TIME_LIMIT_S = 200.0
GRACE_S = 20.0
VERIFY_LIMIT_S = 400.0
DEV_CASES = [f'case_{i:04d}' for i in range(1, 5)]
N_PARALLEL = max(1, min(4, (os.cpu_count() or 2)))
THREAD_VARS = ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'RAYON_NUM_THREADS')
PACK_VARS = ('REVISIT_PACK', 'DATA_DIR', 'AGENTIC_DATA_DIR')
EXPECTED_SHA256 = {'capture.py': 'cc7a660d33180d61479bbf0df59fae815d0119dd19d9e5290e0d2126096804d5', 'sim.py': '88d556623c35fb0474a8d9f6032896eccb63b501111729bafc4b824cb23f0697', 'revisit_verifier.py': 'aa00cdf596717af9eeeeadc1ac140e1bc2f55bca9fb7bdc1d5294c346c0e2501'}   # capture.py, sim.py and the frozen verifier


def check_integrity():
    for f, h in EXPECTED_SHA256.items():
        if hashlib.sha256(open(os.path.join(HERE, f), 'rb').read()).hexdigest() != h:
            raise RuntimeError(f'integrity check failed: {f} was modified')


def find_pack():
    for v in PACK_VARS:
        p = os.environ.get(v)
        if p and os.path.isdir(os.path.join(p, 'cases', 'train')): return p
    for c in glob.glob('/kaggle/input/**/cases/train', recursive=True):
        return os.path.dirname(os.path.dirname(c))
    if os.path.isdir(os.path.join(HERE, 'data', 'cases')): return os.path.join(HERE, 'data')
    raise FileNotFoundError('data pack not found: set DATA_DIR to the folder that holds cases/')


def _threads1():
    for v in THREAD_VARS: os.environ[v] = '1'


def _child(program_path, case_dir, out_json, st_json):
    _threads1()
    for v in PACK_VARS: os.environ.pop(v, None)
    try:
        sys.path.insert(0, HERE); import sim
        world = sim.build_world(case_dir)
        sys.path.insert(0, os.path.dirname(os.path.abspath(program_path)))
        spec = importlib.util.spec_from_file_location('program', program_path); mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        t0 = time.time(); out = mod.solve(world, TIME_LIMIT_S); dt = time.time() - t0
        import numpy as np
        states = [np.asarray(s, float).reshape(6) for s in out['satellites']]
        acts = [(int(a[0]), int(a[1]), float(a[2]), float(a[3])) for a in out['actions']]
        bad = [a for a in acts if not (0 <= a[0] < len(states) and 0 <= a[1] < len(world['targets']))]
        if bad: raise ValueError(f'action index out of range: {bad[0]}')
        json.dump(sim.to_solution_json(world, states, acts), open(out_json, 'w'))
        json.dump({'ok': True, 'solve_s': round(dt, 2)}, open(st_json, 'w'))
    except BaseException as e:
        json.dump({'ok': False, 'error': f'{type(e).__name__}: {e}'[:1500], 'trace': traceback.format_exc()[-3000:]}, open(st_json, 'w'))


def _verify_child(case_dir, sol_json, res_json):
    _threads1()
    try:
        sys.path.insert(0, HERE); import sim, revisit_verifier as V
        world = sim.build_world(case_dir); r = V.verify_solution(case_dir, sol_json); m = r.metrics or {}; res = {'valid': bool(r.is_valid)}
        if r.is_valid:
            g = [m['target_gap_summary'][t['id']]['max_revisit_gap_hours'] for t in world['targets']]
            req = [t['expected_revisit_period_hours'] for t in world['targets']]
            sol = json.load(open(sol_json)); n = len(sol['satellites'])
            res.update(score=sim.mission_score(world, n, g, True), n_satellites=n, cap=world['cap'], revisit_req_h=req[0] if len(set(req)) == 1 else req,
                       n_targets_missing=int(sum(gi > ri + 1e-9 for gi, ri in zip(g, req))), worst_gap_h=round(max(g), 3),
                       capped_mean_gap_h=m.get('capped_max_revisit_gap_hours'), n_actions=len(sol['actions']))
        else:
            res.update(score=0.0, errors=list(r.errors)[:5])
        json.dump(res, open(res_json, 'w'))
    except BaseException as e:
        json.dump({'valid': False, 'score': 0.0, 'error': f'verifier: {type(e).__name__}: {e}'[:1500]}, open(res_json, 'w'))


def _run(target, args, limit):
    p = mp.get_context('spawn').Process(target=target, args=args); p.start(); p.join(limit)
    if p.is_alive(): p.kill(); p.join(5); return False, p.exitcode
    return True, p.exitcode


def run_case(args):
    program_path, pack, split, case, work = args
    cd = os.path.join(pack, 'cases', split, case); sol = os.path.join(work, f'{case}_solution.json'); st = os.path.join(work, f'{case}_status.json')
    t0 = time.time(); done, code = _run(_child, (program_path, cd, sol, st), TIME_LIMIT_S + GRACE_S); wall = round(time.time() - t0, 1)
    if not done: return case, {'valid': False, 'score': 0.0, 'error': f'time limit exceeded ({TIME_LIMIT_S:.0f} s)', 'wall_s': wall}
    if not os.path.isfile(st): return case, {'valid': False, 'score': 0.0, 'error': f'program process died (exit code {code})', 'wall_s': wall}
    s = json.load(open(st))
    if not s.get('ok'): return case, {'valid': False, 'score': 0.0, 'error': s.get('error'), 'trace': s.get('trace', '')[-1500:], 'wall_s': wall}
    if s['solve_s'] > TIME_LIMIT_S: return case, {'valid': False, 'score': 0.0, 'error': f"solve() took {s['solve_s']} s > {TIME_LIMIT_S:.0f} s", 'wall_s': wall}
    rj = os.path.join(work, f'{case}_verify.json'); done, _ = _run(_verify_child, (cd, sol, rj), VERIFY_LIMIT_S)
    res = json.load(open(rj)) if done and os.path.isfile(rj) else {'valid': False, 'score': 0.0, 'error': 'verifier did not finish'}
    res['solve_s'] = s['solve_s']; res['wall_s'] = round(time.time() - t0, 1)
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
            sc = [per[c]['score'] for c in per]; ok = [per[c] for c in per if per[c].get('valid')]
            metrics = {'combined_score': sum(sc) / len(sc), 'n_valid': len(ok), 'n_cases': len(per),
                       'n_cases_all_targets_met': sum(1 for r in ok if r.get('n_targets_missing') == 0),
                       'total_satellites': sum(r.get('n_satellites', 0) for r in ok),
                       'max_solve_s': max((per[c].get('solve_s') or 0) for c in per), 'per_case': per, 'eval_seconds': round(time.time() - t0, 1)}
            correct = metrics['n_valid'] == metrics['n_cases']; msg = 'ok' if correct else 'some missions invalid or failed (scored 0)'
            print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in metrics.items() if k != 'per_case'}, indent=1))
            for c, r in per.items():
                print(c, {k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items() if k != 'trace'})
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
