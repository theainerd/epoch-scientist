"""Export the two blind-run W&B records into results/wandb/<problem>_<run id>/ through the W&B GraphQL API.
Needs WANDB_API_KEY with read access to the runs. Usage: python analysis/export_wandb.py <wandb_entity>
Writes run_info.json, config.json, wandb-summary.json, history.jsonl (every logged row) and system_metrics.jsonl."""
import os, sys, json, pathlib, requests
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from paths import ROOT
if len(sys.argv) < 2:
    sys.exit('usage: python analysis/export_wandb.py <wandb_entity>')
ENTITY = sys.argv[1]
RUNS = [('aisci-aeossp', 'bcw9vydb', 'aeossp'), ('aisci-revisit', 'z3vvh4ce', 'revisit')]
key = os.environ['WANDB_API_KEY']
for proj, rid, short in RUNS:
    q = ('{ project(name:"%s", entityName:"%s"){ run(name:"%s"){ name displayName state createdAt heartbeatAt config '
         'summaryMetrics history(samples:100000) events(samples:100000) } } }') % (proj, ENTITY, rid)
    r = requests.post('https://api.wandb.ai/graphql', json={'query': q}, auth=('api', key), timeout=120).json()['data']['project']['run']
    out = pathlib.Path(ROOT, 'results', 'wandb', f'{short}_{rid}'); out.mkdir(parents=True, exist_ok=True)
    json.dump({k: r[k] for k in ['name', 'displayName', 'state', 'createdAt', 'heartbeatAt']} | {'project': proj},
              open(out / 'run_info.json', 'w'), indent=1)
    json.dump(json.loads(r['config']), open(out / 'config.json', 'w'), indent=1)
    json.dump(json.loads(r['summaryMetrics']), open(out / 'wandb-summary.json', 'w'), indent=1)
    (out / 'history.jsonl').write_text('\n'.join(r['history']) + '\n')
    (out / 'system_metrics.jsonl').write_text('\n'.join(r['events']) + '\n')
    print(f'{short}: {len(r["history"])} history rows, {len(r["events"])} system rows -> {out}')
