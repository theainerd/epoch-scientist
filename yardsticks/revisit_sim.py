"""Helpers for the revisit-constellation task, using the same physics as the official verifier:
J2-only numerical propagation (brahe), 10 s geometry samples (elevation, slant range, off-nadir), bang-coast-bang slew + settle,
gaps between observation midpoints including the mission start and end."""
import json, math
from datetime import datetime, timedelta, timezone
from pathlib import Path
import numpy as np
import brahe

STEP = 10.0   # verifier ACTION_SAMPLE_STEP_SEC
_EOP = False
def ready():
    global _EOP
    if not _EOP:
        brahe.set_global_eop_provider_from_static_provider(brahe.StaticEOPProvider.from_zero()); _EOP = True

def _dt(s): return datetime.fromisoformat(s.replace('Z', '+00:00')).astimezone(timezone.utc)
def epoch(d):
    d = d.astimezone(timezone.utc)
    return brahe.Epoch.from_datetime(d.year, d.month, d.day, d.hour, d.minute, float(d.second) + d.microsecond / 1e6, 0.0, brahe.TimeSystem.UTC)

def load_case(case_dir):
    case_dir = Path(case_dir); a = json.load(open(case_dir / 'assets.json')); m = json.load(open(case_dir / 'mission.json'))
    t0, t1 = _dt(m['horizon_start']), _dt(m['horizon_end'])
    ready()
    T = []
    for t in m['targets']:
        ecef = np.asarray(brahe.position_geodetic_to_ecef([t['longitude_deg'], t['latitude_deg'], t.get('altitude_m', 0.0)], brahe.AngleFormat.DEGREES), float)
        T.append(dict(t, ecef=ecef))
    return dict(case_dir=str(case_dir), start=t0, end=t1, horizon_s=(t1 - t0).total_seconds(), cap=a['max_num_satellites'], model=a['satellite_model'], targets=T)

def kepler_state(alt_m, inc_deg, raan_deg, ma_deg, ecc=0.0, argp_deg=0.0):
    """ECI state [x,y,z,vx,vy,vz] (m, m/s) at mission start from Keplerian elements (altitude above R_EARTH)."""
    return np.asarray(brahe.state_koe_to_eci(np.array([brahe.R_EARTH + alt_m, ecc, inc_deg, raan_deg, argp_deg, ma_deg]), brahe.AngleFormat.DEGREES), float)

def propagate(case, states):
    """Returns times (s from start, 10 s grid incl. end), positions ECI and ECEF (n_sat, n_t, 3), and the propagators."""
    ready(); e0, e1 = epoch(case['start']), epoch(case['end'])
    fc = brahe.ForceModelConfig(gravity=brahe.GravityConfiguration.spherical_harmonic(2, 0))
    ts = np.arange(0.0, case['horizon_s'] + 1e-9, STEP); eps = [e0 + float(t) for t in ts]
    props, eci, ecef = [], [], []
    for s in states:
        p = brahe.NumericalOrbitPropagator.from_eci(e0, np.asarray(s, float), force_config=fc); p.propagate_to(e1); props.append(p)
        eci.append(np.asarray(p.states_eci(eps), float)[:, :3]); ecef.append(np.asarray(p.states_ecef(eps), float)[:, :3])
    return ts, np.array(eci), np.array(ecef), props

def visible(case, ecef_sat):
    """Boolean (n_target, n_t) for ONE satellite's ECEF track: elevation, slant range (target and sensor) and off-nadir limits."""
    sen = case['model']['sensor']; out = []
    for t in case['targets']:
        tp = t['ecef']; los = ecef_sat - tp; rng = np.linalg.norm(los, axis=1)
        lat, lon = math.radians(t['latitude_deg']), math.radians(t['longitude_deg'])
        up = np.array([math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat)])
        el = np.degrees(np.arcsin(np.clip(los @ up / rng, -1, 1)))
        nad = -ecef_sat; v = tp - ecef_sat
        offn = np.degrees(np.arccos(np.clip(np.sum(nad * v, 1) / (np.linalg.norm(nad, axis=1) * rng), -1, 1)))
        m = 1e-3
        out.append((el >= t['min_elevation_deg'] + m) & (rng <= t['max_slant_range_m'] - 1.0) & (rng <= sen['max_range_m'] - 1.0) & (offn <= sen['max_off_nadir_angle_deg'] - m))
    return np.array(out)

def slew_time(angle_deg, att):
    a = max(0.0, angle_deg)
    if a <= 1e-9: return 0.0
    v, acc = att['max_slew_velocity_deg_per_sec'], att['max_slew_acceleration_deg_per_sec2']; tri = v * v / acc
    return 2 * math.sqrt(a / acc) if a <= tri else 2 * v / acc + (a - tri) / v

def gaps(case, obs_mid_s):
    """obs_mid_s: dict target_index -> list of observation midpoints (s). Returns per-target max gap (h)."""
    H = case['horizon_s']; g = []
    for j in range(len(case['targets'])):
        ts = sorted(set(obs_mid_s.get(j, []))); pts = [0.0] + ts + [H]
        g.append(max(b - a for a, b in zip(pts, pts[1:])) / 3600)
    return np.array(g)

def write_solution(case, states, actions, path):
    iso = lambda s: (case['start'] + timedelta(seconds=float(s))).strftime('%Y-%m-%dT%H:%M:%SZ')
    sats = [dict(satellite_id=f'sat_{i+1:03d}', x_m=float(s[0]), y_m=float(s[1]), z_m=float(s[2]), vx_m_s=float(s[3]), vy_m_s=float(s[4]), vz_m_s=float(s[5])) for i, s in enumerate(states)]
    acts = [dict(action_type='observation', satellite_id=f'sat_{i+1:03d}', target_id=case['targets'][j]['id'], start=iso(a), end=iso(b)) for (i, j, a, b) in sorted(actions, key=lambda q: (q[0], q[2]))]
    Path(path).parent.mkdir(parents=True, exist_ok=True); json.dump(dict(satellites=sats, actions=acts), open(path, 'w'), indent=1)
