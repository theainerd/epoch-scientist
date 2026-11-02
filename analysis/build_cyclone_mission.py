"""Usage: python analysis/build_cyclone_mission.py  (needs `make fetch`; rewrites results/revisit/fresh_missions/cyclone)
Real-world use case: 'cyclone watch' — 30 coastal cities often hit by tropical cyclones, one photo every 6 h for 48 h.
Uses the benchmark's mission format, target defaults and satellite model (copied from a generated case)."""
import csv, json, os, shutil, math
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from paths import ROOT, AAB
HERE = os.path.join(ROOT, 'results', 'revisit', 'fresh_missions')
CITIES = [('Chattogram', 'Bangladesh'), ('Khulna', 'Bangladesh'), ('Kolkāta', 'India'), ('Bhubaneshwar', 'India'),
          ('Vishākhapatnam', 'India'), ('Chennai', 'India'), ('Mumbai', 'India'), ('Karachi', 'Pakistan'),
          ('Rangoon', 'Burma'), ('Manila', 'Philippines'), ('Tacloban', 'Philippines'), ('Huế', 'Vietnam'),
          ('Hong Kong', 'Hong Kong'), ('Shanghai', 'China'), ('Naha', 'Japan'), ('Tokyo', 'Japan'),
          ('Miami', 'United States'), ('Houston', 'United States'), ('New Orleans', 'United States'), ('Havana', 'Cuba'),
          ('San Juan', 'Puerto Rico'), ('Port-au-Prince', 'Haiti'), ('Santo Domingo', 'Dominican Republic'),
          ('Beira', 'Mozambique'), ('Toamasina', 'Madagascar'), ('Darwin', 'Australia'), ('Cairns', 'Australia'),
          ('Suva', 'Fiji'), ('Muscat', 'Oman'), ('Port Louis', 'Mauritius')]
rows = list(csv.DictReader(open(os.path.join(AAB, 'benchmarks', 'revisit_constellation', 'sources', 'world_cities.csv'), encoding='utf-8')))
def find(name, country):
    c = [r for r in rows if r['name'].lower() == name.lower() and r['country'].lower() == country.lower()]
    if not c: MISSING.append((name, country)); return None
    return max(c, key=lambda r: float(r['population'] or 0))
ref = json.load(open(os.path.join(HERE, 'cases', 'test', 'case_0002', 'mission.json')))  # a 6 h generated case
tdef = {k: ref['targets'][0][k] for k in ('altitude_m', 'max_slant_range_m', 'min_duration_sec', 'min_elevation_deg')}
targets = []; MISSING = []
for i, (n, ctry) in enumerate(CITIES, 1):
    r = find(n, ctry)
    if r is None: continue
    targets.append(dict(tdef, expected_revisit_period_hours=6.0, id=f'target_{i:03d}', latitude_deg=round(float(r['latitude_deg']), 4),
                        longitude_deg=round(float(r['longitude_deg']), 4), name=f"{r['name']}, {r['country']}"))
def sep(a, b):
    p1, p2 = math.radians(a['latitude_deg']), math.radians(b['latitude_deg']); dl = math.radians(b['longitude_deg'] - a['longitude_deg'])
    return 6371e3 * math.acos(min(1, math.sin(p1) * math.sin(p2) + math.cos(p1) * math.cos(p2) * math.cos(dl)))
print('missing', MISSING)
mins = min(sep(a, b) for i, a in enumerate(targets) for b in targets[i + 1:])
out = os.path.join(HERE, 'cyclone', 'cases', 'test', 'case_0001'); os.makedirs(out, exist_ok=True)
json.dump(dict(horizon_start=ref['horizon_start'], horizon_end=ref['horizon_end'], targets=targets), open(os.path.join(out, 'mission.json'), 'w'), indent=2)
a = json.load(open(os.path.join(HERE, 'cases', 'test', 'case_0002', 'assets.json'))); a['max_num_satellites'] = 20
json.dump(a, open(os.path.join(out, 'assets.json'), 'w'), indent=2)
print(len(targets), 'targets; min separation km', round(mins / 1e3), '; |lat| max', max(abs(t['latitude_deg']) for t in targets))
print([t['name'] for t in targets][:6], '...')
