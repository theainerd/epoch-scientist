"""Export the replay of one Revisit mission for the before/after video: exact verifier propagation of the submitted satellites,
photo midpoints from the submitted plans, and per-target overdue state. Checks the counts against the official verifier output."""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import ROOT, AAB, WORK, ASSETS, FFMPEG, AEOSSP_PACK, REVISIT_DATA  # noqa: E402,F401
import json, sys, math
from datetime import datetime, timezone
import numpy as np
sys.path.insert(0, _os.path.join(ROOT, 'tasks', 'revisit')); import sim
SPLIT, CASE = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else ('test', 'case_0004')
D = _os.path.join(REVISIT_DATA, 'cases')
S = _os.path.join(WORK, 'sealed', 'revisit')
w = sim.build_world(f'{D}/{SPLIT}/{CASE}'); H = w['horizon_s']; tid = {t['id']: j for j, t in enumerate(w['targets'])}
FT = np.arange(0.0, H + 1, 120.0)                    # frame times (s): 48 h at 2 min per frame
def ll(ecef):
    x, y, z = ecef[..., 0], ecef[..., 1], ecef[..., 2]
    return np.degrees(np.arctan2(z, np.hypot(x, y))), np.degrees(np.arctan2(y, x))
out = dict(case=f'{SPLIT}/{CASE}', horizon_s=H, cap=w['cap'], frame_t=FT.tolist(),
           targets=[dict(lat=t['latitude_deg'], lon=t['longitude_deg'], req_h=t['expected_revisit_period_hours'], name=t.get('name', t['id'])) for t in w['targets']])
for key, tag in (('start', 'p0'), ('muse', 'w2c10')):
    sol = json.load(open(f'{S}/{tag}_{SPLIT}/_cases/{CASE}_solution.json')); ver = json.load(open(f'{S}/{tag}_{SPLIT}/_cases/{CASE}_verify.json'))
    st = [np.array([s['x_m'], s['y_m'], s['z_m'], s['vx_m_s'], s['vy_m_s'], s['vz_m_s']]) for s in sol['satellites']]
    eci, ecef, _ = sim.exact_propagate(w, st)
    idx = np.searchsorted(w['times'], FT); la, lo = ll(ecef[:, idx, :])                    # (n_sat, n_frames)
    t0 = w['start']; sec = lambda s: (datetime.fromisoformat(s.replace('Z', '+00:00')) - t0).total_seconds()
    photos = [dict(sat=int(a['satellite_id'][4:]) - 1, tgt=tid[a['target_id']], mid=(sec(a['start']) + sec(a['end'])) / 2) for a in sol['actions']]
    mids = {}
    for p in photos: mids.setdefault(p['tgt'], []).append(p['mid'])
    g = sim.max_gaps_hours(w, mids); req = np.array([t['expected_revisit_period_hours'] for t in w['targets']])
    miss = int((g > req + 1e-9).sum())
    assert miss == ver['n_targets_missing'], (key, miss, ver['n_targets_missing']); assert abs(g.max() - ver['worst_gap_h']) < 1e-3
    import brahe
    K = np.array([np.asarray(brahe.state_eci_to_koe(x, brahe.AngleFormat.DEGREES)) for x in st]); raan = np.round(K[:, 3] / 3) * 3 % 360
    planes = len(set(raan.tolist())); alt = (K[:, 0] - brahe.R_EARTH) / 1e3; inc = float(np.median(K[:, 2]))
    layout = dict(planes=planes, per_plane=round(len(st) / planes, 1), inc_deg=round(inc, 1), alt_km=int(round(float(np.median(alt)), -1)))
    out[key] = dict(layout=layout, n_sat=len(st), lat=np.round(la, 3).tolist(), lon=np.round(lo, 3).tolist(), photos=photos, valid=ver['valid'], score=ver['score'],
                    n_missing=miss, worst_gap_h=float(g.max()), n_never=int(sum(1 for j in range(len(w['targets'])) if j not in mids)))
    print(key, layout, 'sats', len(st), 'photos', len(photos), 'targets missing', miss, 'never photographed', out[key]['n_never'], 'worst gap h', round(g.max(), 2), 'score', round(ver['score'], 3))
print('targets', len(w['targets']), 'req', sorted(set(req.tolist())), 'cap', w['cap'], 'lat range', round(min(t['latitude_deg'] for t in w['targets']), 1), round(max(t['latitude_deg'] for t in w['targets']), 1))
json.dump(out, open(_os.path.join(_os.makedirs(_os.path.join(WORK, 'viz', 'revisit'), exist_ok=True) or _os.path.join(WORK, 'viz', 'revisit'), f'replay_{SPLIT}{int(CASE[-4:])}.json'), 'w'))
