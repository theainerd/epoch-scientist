"""Export one AEOSSP case as a 'world pack' for the blind discovery task.
Physics only: opportunities (= single observations that already satisfy window, duration, sensor,
visibility and off-nadir rules), pointing vectors, nadir-slew times, sunlit flags. No search method."""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import ROOT, AAB, WORK, ASSETS, FFMPEG, AEOSSP_PACK, REVISIT_DATA  # noqa: E402,F401
import sys, json, time, numpy as np
from datetime import timedelta
from pathlib import Path
sys.path.insert(0, _os.path.join(AAB, 'solvers/aeossp_standard/mwis_conflict_graph'))
from src.case_io import load_case
from src.candidates import CandidateConfig, generate_candidates
from src.geometry import PropagationContext
from src.transition import TransitionVectorCache
from src.validation import is_sunlit, _initial_slew_required_s

split, cid = sys.argv[1], sys.argv[2]
cd = Path(AAB) / 'benchmarks/aeossp_standard/dataset/cases' / split / cid
out = Path(AEOSSP_PACK) / 'worlds' / split / cid; out.mkdir(parents=True, exist_ok=True)
t0 = time.time(); case = load_case(cd); m = case.mission
cands, _ = generate_candidates(case, CandidateConfig())
cands = sorted(cands, key=lambda c: (c.satellite_id, c.start_offset_s, c.task_id))
sat_ids = sorted(case.satellites); task_ids = sorted(case.tasks)
si = {s: i for i, s in enumerate(sat_ids)}; ti = {t: i for i, t in enumerate(task_ids)}
prop = PropagationContext(case.satellites, step_s=m.geometry_sample_step_s); vc = TransitionVectorCache(case, prop)
n = len(cands); ls = np.zeros((n, 3)); le = np.zeros((n, 3)); ini = np.zeros(n)
for k, c in enumerate(cands):
    a, b = vc.vector(c, 'start'), vc.vector(c, 'end')
    ls[k] = a / np.linalg.norm(a); le[k] = b / np.linalg.norm(b)
    ini[k] = _initial_slew_required_s(case, c, propagation=prop)
H = int(m.horizon_seconds); step = int(m.resource_sample_step_s)
grid = np.arange(0, H, step)
sun = np.array([[is_sunlit(prop, s, float(t), case) for t in grid] for s in sat_ids], dtype=bool)
np.savez_compressed(out / 'world.npz',
    sat=np.array([si[c.satellite_id] for c in cands], np.int16), task=np.array([ti[c.task_id] for c in cands], np.int32),
    start_s=np.array([c.start_offset_s for c in cands], np.int32), end_s=np.array([c.end_offset_s for c in cands], np.int32),
    look_start=ls.astype(np.float64), look_end=le.astype(np.float64), nadir_slew_s=ini, sunlit=sun, sunlit_step_s=np.int32(step))
sats = []
for s in sat_ids:
    S = case.satellites[s]; am, rm = S.attitude_model, S.resource_model
    sats.append(dict(id=s, sensor=S.sensor_type if hasattr(S, 'sensor_type') else None,
        max_slew_velocity_deg_per_s=am.max_slew_velocity_deg_per_s, max_slew_acceleration_deg_per_s2=am.max_slew_acceleration_deg_per_s2,
        settling_time_s=am.settling_time_s, battery_capacity_wh=rm.battery_capacity_wh, initial_battery_wh=rm.initial_battery_wh,
        idle_power_w=rm.idle_power_w, imaging_power_w=rm.imaging_power_w, slew_power_w=rm.slew_power_w, sunlit_charge_power_w=rm.sunlit_charge_power_w))
hs = m.horizon_start
tasks = [dict(id=t, weight=case.tasks[t].weight, release_s=(case.tasks[t].release_time - hs).total_seconds(), due_s=(case.tasks[t].due_time - hs).total_seconds(),
              duration_s=case.tasks[t].required_duration_s, sensor=case.tasks[t].required_sensor_type,
              lat_deg=case.tasks[t].latitude_deg, lon_deg=case.tasks[t].longitude_deg) for t in task_ids]
json.dump(dict(case=f'{split}/{cid}', horizon_s=H, action_time_step_s=int(m.action_time_step_s), n_opportunities=n,
               satellites=sats, tasks=tasks), open(out / 'world.json', 'w'))
print(json.dumps(dict(case=f'{split}/{cid}', n=n, sats=len(sat_ids), tasks=len(task_ids), secs=round(time.time() - t0, 1))))
