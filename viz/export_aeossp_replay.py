"""Export one AEOSSP mission + two plans into data files for the CesiumJS viewer.

Every value comes from the frozen official verifier (task_aeossp/aab_verifier.py, unchanged):
  ACTUAL  satellite positions: verifier SGP4 propagator (brahe), Earth-fixed (ITRF) metres, sampled every STEP_S
  ACTUAL  photo events:        verifier-validated observation actions (satellite, task, start, end)
  ACTUAL  slew windows:        verifier maneuver windows (turn + settle before each photo)
  ACTUAL  battery:             verifier battery-trace segments (piecewise linear); colinear interior points removed (lossless)
  ACTUAL  sunlight:            segments where the verifier applied solar charging power
  ACTUAL  validity, violations, metrics; score N from the paper formula applied to verifier metrics (same as evaluate.py)
  DERIVED (in the viewer, documented): ground tracks (geodetic sub-satellite point of the actual positions),
          camera pointing line (straight line satellite->target during each actual photo), running counters.
Usage: python export_viz.py <split> <case> <baseline_solution.json> <muse_solution.json> <out_dir>
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import ROOT, AAB, WORK, ASSETS, FFMPEG, AEOSSP_PACK, REVISIT_DATA  # noqa: E402,F401
import sys, json, math, hashlib
from datetime import timedelta
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
TASK = Path(ROOT) / 'tasks' / 'aeossp'
sys.path.insert(0, str(TASK))
import aab_verifier as V

STEP_S = 30
split, case_id, sol_base, sol_muse, out = sys.argv[1:6]
CASE = Path(AAB) / 'benchmarks/aeossp_standard/dataset/cases' / split / case_id
out = Path(out); out.mkdir(parents=True, exist_ok=True)
case = V.load_case(CASE); m = case.mission; h0 = m.horizon_start
H = (m.horizon_end - h0).total_seconds()
sec = lambda t: round((t - h0).total_seconds(), 3)
iso = lambda t: t.strftime('%Y-%m-%dT%H:%M:%SZ')
sat_ids = sorted(case.satellites); task_ids = sorted(case.tasks)
E_bud = sum(s.resource_model.battery_capacity_wh for s in case.satellites.values())

# ---- satellites: actual positions (Earth-fixed) from the verifier's propagator -> CZML
V._ensure_brahe_ready()                       # same EOP setup as the verifier (aab_verifier.py line 1423)
prop = V._PropagationContext(case)          # same construction as the verifier (aab_verifier.py line 1424)
czml = [{'id': 'document', 'name': f'{split}/{case_id}', 'version': '1.0',
         'clock': {'interval': f'{iso(h0)}/{iso(m.horizon_end)}', 'currentTime': iso(h0), 'multiplier': 60, 'range': 'CLAMPED', 'step': 'SYSTEM_CLOCK_MULTIPLIER'}}]
pos_out = {}
for s in sat_ids:
    arr = []
    for k in range(int(H // STEP_S) + 1):
        t = h0 + timedelta(seconds=k * STEP_S)
        p = prop.state_ecef(s, t)[:3]
        arr += [k * STEP_S, round(float(p[0]), 1), round(float(p[1]), 1), round(float(p[2]), 1)]
    pos_out[s] = arr
    czml.append({'id': s, 'name': s, 'availability': f'{iso(h0)}/{iso(m.horizon_end)}',
                 'position': {'epoch': iso(h0), 'referenceFrame': 'FIXED', 'interpolationAlgorithm': 'LAGRANGE', 'interpolationDegree': 5, 'cartesian': arr},
                 'point': {'pixelSize': 6, 'color': {'rgba': [255, 255, 255, 255]}, 'outlineColor': {'rgba': [20, 20, 20, 255]}, 'outlineWidth': 1},
                 'label': {'text': s.replace('sat_', ''), 'font': '11px sans-serif', 'pixelOffset': {'cartesian2': [8, -8]}, 'fillColor': {'rgba': [230, 230, 230, 255]}, 'showBackground': False},
                 'path': {'show': True, 'leadTime': 0, 'trailTime': 1800, 'width': 1, 'resolution': 60, 'material': {'solidColor': {'color': {'rgba': [180, 200, 230, 110]}}}}})

# ---- targets
tasks = [{'id': t, 'w': case.tasks[t].weight, 'lat': case.tasks[t].latitude_deg, 'lon': case.tasks[t].longitude_deg,
          'r': sec(case.tasks[t].release_time), 'd': sec(case.tasks[t].due_time), 'sensor': case.tasks[t].required_sensor_type} for t in task_ids]
ti = {t: i for i, t in enumerate(task_ids)}; si = {s: i for i, s in enumerate(sat_ids)}

def plan(sol_path, label):
    a = V.analyze_solution(CASE, sol_path); r = a.result
    obs = sorted(([si[x.satellite_id], ti[x.task_id], sec(x.start_time), sec(x.end_time)] for x in a.validated_actions), key=lambda q: q[2])
    mw = a.maneuver_windows; mw = [w for v in mw.values() for w in v] if isinstance(mw, dict) else list(mw)
    slews = sorted(([si[w.satellite_id], sec(w.start_time), sec(w.end_time), round(w.slew_angle_deg, 2)] for w in mw), key=lambda q: q[1])
    bat, sun = {}, {}
    for s in sat_ids:
        segs = a.battery_traces.get(s, ())
        t = [sec(x.start_time) for x in segs] + ([sec(segs[-1].end_time)] if segs else [])
        b = [x.battery_start_wh for x in segs] + ([segs[-1].battery_end_wh] if segs else [])
        keep = [0] + [i for i in range(1, len(t) - 1) if abs((b[i] - b[i-1]) / max(t[i] - t[i-1], 1e-9) - (b[i+1] - b[i]) / max(t[i+1] - t[i], 1e-9)) > 1e-9] + ([len(t) - 1] if len(t) > 1 else [])
        bat[si[s]] = [[t[i], round(b[i], 3)] for i in keep]
        iv = []
        for x in segs:
            if x.charge_power_w > 0:
                a0, a1 = sec(x.start_time), sec(x.end_time)
                if iv and abs(iv[-1][1] - a0) < 1e-6: iv[-1][1] = a1
                else: iv.append([a0, a1])
        sun[si[s]] = iv
    fails = [[si[f.satellite_id], sec(f.time), f.reason] for f in a.action_failures]
    mt = r.metrics; cl = lambda x: min(1.0, max(0.0, x))
    N = 100 * (0.45 * mt['WCR'] + 0.20 * mt['CR'] + 0.20 * cl(1 - mt['TAT'] / H) + 0.15 * cl(1 - mt['PC'] / E_bud)) if r.valid and mt.get('TAT') is not None else 0.0
    sim_end = {si[s]: (sec(a.battery_traces[s][-1].end_time) if a.battery_traces.get(s) else H) for s in sat_ids}
    print(label, 'valid', r.valid, 'N', round(N, 3), 'obs', len(obs), 'slews', len(slews), 'battery pts', sum(len(v) for v in bat.values()), 'failures', len(fails))
    return {'label': label, 'solution_sha256': hashlib.sha256(Path(sol_path).read_bytes()).hexdigest(), 'valid': bool(r.valid), 'N': N, 'metrics': mt,
            'violations': list(r.violations), 'obs': obs, 'slews': slews, 'battery': bat, 'sun': sun, 'failures': fails, 'sim_end': sim_end,
            'min_battery': {sat_ids[k]: min(p[1] for p in v) for k, v in bat.items() if v}}

replay = {'mission': {'split': split, 'case': case_id, 'start': iso(h0), 'end': iso(m.horizon_end), 'horizon_s': H, 'energy_budget_wh': E_bud, 'pos_step_s': STEP_S},
          'satellites': [{'id': s, 'sensor': case.satellites[s].sensor.sensor_type, 'cap_wh': case.satellites[s].resource_model.battery_capacity_wh,
                          'init_wh': case.satellites[s].resource_model.initial_battery_wh} for s in sat_ids],
          'tasks': tasks, 'plans': {'baseline': plan(sol_base, 'Starting program (baseline)'), 'muse': plan(sol_muse, 'Muse-evolved program')},
          'provenance': {'verifier': 'task_aeossp/aab_verifier.py (frozen official AstroAgentBench aeossp_standard verifier)',
                         'verifier_sha256': hashlib.sha256((TASK / 'aab_verifier.py').read_bytes()).hexdigest(), 'case_dir': str(CASE),
                         'derived_in_viewer': ['ground track = geodetic sub-satellite point of actual positions', 'camera pointing = straight line satellite->target during each actual photo interval', 'running counters (photos, value) = cumulative sums of actual verifier-validated actions']}}
(out / 'mission.czml').write_text(json.dumps(czml))
(out / 'replay.json').write_text(json.dumps(replay, separators=(',', ':')))
(out / 'data.js').write_text('window.SAT_CZML=' + json.dumps(czml, separators=(',', ':')) + ';\nwindow.REPLAY=' + json.dumps(replay, separators=(',', ':')) + ';\n')
print('wrote', {f.name: round(f.stat().st_size / 1e6, 2) for f in out.iterdir()})
