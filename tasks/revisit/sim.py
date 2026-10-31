"""Helper library for the constellation design task (free to import from program.py). Physics only.

`world` (built by the evaluator, one mission):
  start, end            mission start/end (datetime, UTC); horizon_s = 172800 (48 h)
  cap                   maximum number of satellites allowed
  model                 satellite model: sensor (max_off_nadir_angle_deg, max_range_m, obs_discharge_rate_w),
                        attitude_model (slew limits, settling_time_sec, maneuver_discharge_rate_w), resource_model (battery),
                        min_altitude_m / max_altitude_m (perigee and apogee must stay inside, Earth radius = sim.R_EARTH)
  targets               list of dicts: id, name, latitude_deg, longitude_deg, altitude_m, expected_revisit_period_hours,
                        min_elevation_deg, max_slant_range_m, min_duration_sec, ecef (np.array, m)
  times                 np.array of seconds from start on the 10 s grid (0 .. horizon_s), length T
  rot                   (T, 3, 3) rotation matrices inertial (ECI) -> Earth-fixed (ECEF) on that grid

Physics = the official verifier's: J2-only numerical propagation from the ECI initial state at mission start; an observation of
target j from start s to end e is valid if, at s, s+10, s+20, ... (< e), elevation >= min_elevation_deg, slant range <= both
limits and off-nadir angle <= max_off_nadir_angle_deg; e - s >= min_duration_sec; on one satellite, consecutive observations
need e_prev + slew_time(angle) + settling_time <= s_next (angle between the line-of-sight vectors at the two midpoints);
no overlapping actions; battery never below 0. Gaps per target: between observation midpoints, plus mission start and end.
"""
import json, math, os, tempfile
from datetime import timedelta
import numpy as np
import brahe

R_EARTH, GM_EARTH, J2 = brahe.R_EARTH, brahe.GM_EARTH, brahe.J2_EARTH
STEP_S = 10.0
brahe.set_global_eop_provider_from_static_provider(brahe.StaticEOPProvider.from_zero())   # same as the verifier

def build_world(case_dir):
    """Load one mission folder (assets.json + mission.json) into the `world` dict described above."""
    from datetime import datetime, timezone
    from pathlib import Path
    dt = lambda s: datetime.fromisoformat(s.replace('Z', '+00:00')).astimezone(timezone.utc)
    case_dir = Path(case_dir); a = json.load(open(case_dir / 'assets.json')); m = json.load(open(case_dir / 'mission.json'))
    t0, t1 = dt(m['horizon_start']), dt(m['horizon_end']); targets = []
    for t in m['targets']:
        e = np.asarray(brahe.position_geodetic_to_ecef([t['longitude_deg'], t['latitude_deg'], t.get('altitude_m', 0.0)], brahe.AngleFormat.DEGREES), float)
        targets.append(dict(t, ecef=e))
    w = dict(case_dir=str(case_dir), start=t0, end=t1, horizon_s=(t1 - t0).total_seconds(), cap=int(a['max_num_satellites']), model=a['satellite_model'], targets=targets)
    w['times'] = np.arange(0.0, w['horizon_s'] + 1e-9, STEP_S); e0 = epoch(w)
    w['rot'] = np.array([np.asarray(brahe.rotation_eci_to_ecef(e0 + float(x)), float) for x in w['times']])
    return w

def epoch(world, t_s=0.0):
    d = world['start']
    return brahe.Epoch.from_datetime(d.year, d.month, d.day, d.hour, d.minute, float(d.second) + d.microsecond / 1e6, 0.0, brahe.TimeSystem.UTC) + float(t_s)

# ---------------- orbits ----------------
def state_from_elements(alt_m, inc_deg, raan_deg, mean_anomaly_deg, ecc=0.0, argp_deg=0.0):
    """ECI initial state [x, y, z, vx, vy, vz] (m, m/s) from MEAN orbital elements (a = R_EARTH + alt_m).
    Use the same elements in fast_positions() for screening; the two agree to about 5-30 km over 48 h.
    The verifier checks the altitude band on the INSTANTANEOUS perigee/apogee of this state, which can differ from the mean
    altitude by several km: check sim.orbit_altitudes(state) against the band before using a state."""
    mean = np.array([R_EARTH + alt_m, ecc, inc_deg, raan_deg, argp_deg, mean_anomaly_deg])
    osc = np.asarray(brahe.state_koe_mean_to_osc(mean, brahe.MeanElementMethod.BROUWER_LYDDANE, brahe.AngleFormat.DEGREES), float)
    return np.asarray(brahe.state_koe_to_eci(osc, brahe.AngleFormat.DEGREES), float)

def orbit_altitudes(state):
    """(perigee_alt_m, apogee_alt_m) of an ECI state, as the verifier computes them."""
    r, v = np.asarray(state[:3], float), np.asarray(state[3:], float); rn, vn = np.linalg.norm(r), np.linalg.norm(v)
    a = -GM_EARTH / (2 * (0.5 * vn * vn - GM_EARTH / rn)); ev = ((vn * vn - GM_EARTH / rn) * r - np.dot(r, v) * v) / GM_EARTH; e = np.linalg.norm(ev)
    return a * (1 - e) - R_EARTH, a * (1 + e) - R_EARTH

def fast_positions(world, elements):
    """Approximate ECEF tracks (n, T, 3) for a list of mean-element tuples (alt_m, inc_deg, raan_deg, mean_anomaly_deg[, ecc, argp_deg]),
    using secular J2 drift. About 1 ms per satellite. Error vs exact propagation: about 5-30 km over 48 h for near-circular orbits (footprint radius is several hundred km)."""
    ts = world['times']; out = []
    for el in elements:
        alt, inc, raan, ma = el[:4]; ecc = el[4] if len(el) > 4 else 0.0; argp = el[5] if len(el) > 5 else 0.0
        a = R_EARTH + alt; n = math.sqrt(GM_EARTH / a ** 3); p = a * (1 - ecc ** 2); f = 1.5 * J2 * (R_EARTH / p) ** 2; ci = math.cos(math.radians(inc))
        O = math.radians(raan) - f * n * ci * ts
        w = math.radians(argp) + 0.5 * f * n * (5 * ci ** 2 - 1) * ts
        M = math.radians(ma) + n * (1 + 0.5 * f * math.sqrt(1 - ecc ** 2) * (3 * ci ** 2 - 1)) * ts
        E = M.copy()
        for _ in range(8): E = E - (E - ecc * np.sin(E) - M) / (1 - ecc * np.cos(E))
        nu = 2 * np.arctan2(math.sqrt(1 + ecc) * np.sin(E / 2), math.sqrt(1 - ecc) * np.cos(E / 2)); rr = a * (1 - ecc * np.cos(E)); u = w + nu; i = math.radians(inc)
        r = np.stack([np.cos(O) * np.cos(u) - np.sin(O) * np.sin(u) * math.cos(i), np.sin(O) * np.cos(u) + np.cos(O) * np.sin(u) * math.cos(i), np.sin(u) * math.sin(i)], 1) * rr[:, None]
        out.append(np.einsum('tij,tj->ti', world['rot'], r))
    return np.array(out)

def exact_propagate(world, states):
    """Exact (verifier) propagation. Returns (eci (n,T,3), ecef (n,T,3), propagators). About 1 s per satellite on a fast CPU.
    ECEF = world['rot'] applied to ECI (identical to brahe's own conversion to < 1 mm)."""
    e0, e1 = epoch(world), epoch(world, world['horizon_s'])
    fc = brahe.ForceModelConfig(gravity=brahe.GravityConfiguration.spherical_harmonic(2, 0)); eps = [e0 + float(t) for t in world['times']]
    props, eci, ecef = [], [], []
    for s in states:
        p = brahe.NumericalOrbitPropagator.from_eci(e0, np.asarray(s, float), force_config=fc); p.propagate_to(e1); props.append(p)
        eci.append(np.asarray(p.states_eci(eps), float)[:, :3])
    eci = np.array(eci) if eci else np.zeros((0, len(world['times']), 3))
    return eci, np.einsum('tij,ntj->nti', world['rot'], eci), props

# ---------------- geometry ----------------
def visible(world, ecef_track, margin_deg=1e-3):
    """Boolean (n_targets, T): target j observable from this satellite track at each grid time (all geometry limits)."""
    sen = world['model']['sensor']; out = []
    for t in world['targets']:
        tp = t['ecef']; los = ecef_track - tp; rng = np.linalg.norm(los, axis=1)
        lat, lon = math.radians(t['latitude_deg']), math.radians(t['longitude_deg'])
        up = np.array([math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat)])
        el = np.degrees(np.arcsin(np.clip(los @ up / rng, -1, 1)))
        offn = np.degrees(np.arccos(np.clip(np.sum(-ecef_track * (tp - ecef_track), 1) / (np.linalg.norm(ecef_track, axis=1) * rng), -1, 1)))
        out.append((el >= t['min_elevation_deg'] + margin_deg) & (rng <= t['max_slant_range_m'] - 1.0) & (rng <= sen['max_range_m'] - 1.0) & (offn <= sen['max_off_nadir_angle_deg'] - margin_deg))
    return np.array(out)

def slew_time(angle_deg, world):
    att = world['model']['attitude_model']; a = max(0.0, angle_deg)
    if a <= 1e-9: return 0.0
    v, acc = att['max_slew_velocity_deg_per_sec'], att['max_slew_acceleration_deg_per_sec2']; tri = v * v / acc
    return 2 * math.sqrt(a / acc) if a <= tri else 2 * v / acc + (a - tri) / v

def line_of_sight_eci(world, propagator, target_index, t_s):
    """Inertial vector satellite -> target at time t_s (exact propagator), for slew angles."""
    ep = epoch(world, t_s); sat = np.asarray(propagator.state_eci(ep), float)[:3]
    return np.asarray(brahe.position_ecef_to_eci(ep, world['targets'][target_index]['ecef']), float) - sat

def angle_deg(u, v):
    return math.degrees(math.acos(max(-1.0, min(1.0, float(np.dot(u, v) / (np.linalg.norm(u) * np.linalg.norm(v)))))))

# ---------------- score ----------------
def max_gaps_hours(world, midpoints_by_target):
    """midpoints_by_target: dict target_index -> observation midpoints (s). Returns per-target max gap (h), boundaries included."""
    H = world['horizon_s']; g = []
    for j in range(len(world['targets'])):
        pts = [0.0] + sorted(set(midpoints_by_target.get(j, []))) + [H]; g.append(max(b - a for a, b in zip(pts, pts[1:])) / 3600.0)
    return np.array(g)

def mission_score(world, n_satellites, max_gaps_h, valid=True):
    """Task score for one mission (same rule as evaluate.py). 0 if invalid.
    If any target misses its revisit period: 70 * mean_j phi(g_j), phi = 1 if g <= req else ((H-g)/(H-req))^2.
    If every target meets it: 70 + 30 * (cap - n) / (cap - 1)."""
    if not valid or n_satellites < 1: return 0.0
    H = world['horizon_s'] / 3600.0; req = np.array([t['expected_revisit_period_hours'] for t in world['targets']]); g = np.asarray(max_gaps_h, float)
    if np.all(g <= req + 1e-9):
        return 70.0 + 30.0 * (world['cap'] - n_satellites) / max(world['cap'] - 1, 1)
    phi = np.where(g <= req, 1.0, np.clip((H - g) / (H - req), 0, 1) ** 2); return 70.0 * float(phi.mean())

def to_solution_json(world, states, actions):
    iso = lambda s: (world['start'] + timedelta(seconds=float(s))).strftime('%Y-%m-%dT%H:%M:%SZ') if float(s).is_integer() else \
        (world['start'] + timedelta(seconds=float(s))).isoformat().replace('+00:00', 'Z')
    sats = [dict(satellite_id=f'sat_{i+1:03d}', x_m=float(s[0]), y_m=float(s[1]), z_m=float(s[2]), vx_m_s=float(s[3]), vy_m_s=float(s[4]), vz_m_s=float(s[5])) for i, s in enumerate(states)]
    acts = [dict(action_type='observation', satellite_id=f'sat_{int(i)+1:03d}', target_id=world['targets'][int(j)]['id'], start=iso(a), end=iso(b)) for (i, j, a, b) in sorted(actions, key=lambda q: (q[0], q[2]))]
    return dict(satellites=sats, actions=acts)

def official_check(world, states, actions):
    """Run the frozen official verifier on a candidate (exact; about 10-20 s). Returns (valid, metrics, errors, score)."""
    import revisit_verifier as V, shutil
    d = tempfile.mkdtemp(prefix='chk_'); p = os.path.join(d, 'solution.json'); json.dump(to_solution_json(world, states, actions), open(p, 'w'))
    try: r = V.verify_solution(world['case_dir'], p)
    finally: shutil.rmtree(d, ignore_errors=True)
    m = r.metrics or {}
    g = np.array([m['target_gap_summary'][t['id']]['max_revisit_gap_hours'] for t in world['targets']]) if r.is_valid else None
    return r.is_valid, m, list(r.errors)[:10], mission_score(world, len(states), g, r.is_valid) if r.is_valid else 0.0
