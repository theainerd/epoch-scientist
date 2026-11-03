"""Replay the Kaggle notebook log of a discovery run as a readable timeline.
Usage: python demo/replay_notebook.py results/revisit/notebook/aisci-revisit-blind-run.log [--cost results/revisit/notebook/cost_summary.json] [--jsonl OUT]
Every printed line comes from the log. Heartbeat and usage JSON lines are shown as their key fields; long command lines end in '...';
blocks that carry no information for a viewer (download progress, agsci doctor checks, W&B lines that name the
private workspace) are replaced by a visible '[... N lines skipped: reason ...]' marker. Times are seconds since the notebook started."""
import json, re, sys
path = sys.argv[1]; arg = lambda k: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else None
L = json.load(open(path)); T0 = L[0]['time']
B, D, G = '\033[1m', '\033[2m', '\033[0m'
rows, skip = [], {'n': 0, 'why': None, 't': 0}
def cut(x, n=118): return x if len(x) <= n else x[:n - 3] + '...'
def emit(t, text, meta=None):
    if skip['n']: rows.append((skip['t'], f"{D}[... {skip['n']} line{'s' if skip['n'] > 1 else ''} skipped: {skip['why']} ...]{G}", None)); skip['n'] = 0
    rows.append((t, text, meta))
def hide(t, why):
    if skip['n'] and skip['why'] != why: emit(skip['t'], None)
    if not skip['n']: skip['t'] = t
    skip['n'] += 1; skip['why'] = why
for x in L:
    t = x['time'] - T0
    for ln in x.get('data', '').splitlines():
        s = ln.strip()
        if not s: continue
        if 'surya' in s or 'private-workspace' in s or s.startswith('wandb: View') or 'View run' in s or 'View project' in s or 'W&B dashboard' in s:
            hide(t, 'W&B lines naming a private workspace'); continue
        if re.match(r'^[\s%0-9.kMG:/\-]+$', s) or s.startswith(('% Total', 'Dload')): hide(t, 'download progress'); continue
        if re.match(r'^(ok|WARN|FAIL)\s', s) or s.startswith('->') or s == 'agsci doctor' or re.match(r'^\d+ ok, ', s): hide(t, 'agsci doctor checks (docker not used: container.enabled=false)'); continue
        if 'SyntaxWarning' in s or 'NbConvertApp' in s or s.startswith(('cells[i]', 'text = re.sub')): hide(t, 'notebook export messages'); continue
        if s.startswith(('evaluation outputs:', 'evaluation runtime:')) or '[INFO]' in s or s.startswith(('iew:', 'patching file')): hide(t, 'harness bookkeeping'); continue
        if re.search(r"\] tokens \{'input': 0", s): hide(t, 'token counter not wired in this runner version (cost below is Meta-reported)'); continue
        if s.startswith('{"usage"'):
            g = lambda k: (re.search(r'"%s":"?([^",}]+)' % k, s) or [None, '?'])[1]
            tot = g('total'); cost = f" · ${float(tot):.3f} Meta-reported" if tot not in ('?', 'null') else ''
            ntok = sum(int(g(k)) for k in ('inputTokens', 'cacheReadTokens', 'outputTokens') if g(k).isdigit())
            emit(t, f"    {D}usage: model {g('model')} · {ntok:,} tokens{cost}{G}"); continue
        m = re.match(r'^\[\s*([\d.]+) min\] heartbeat (\{.*)$', s)
        if m:
            f = lambda k: (lambda r: float(r.group(1)) if r else None)(re.search(r'"%s": ([\d.]+)' % re.escape(k), m.group(2)))
            c, n, b = f('cost/reported_cost_usd'), int(f('attempts_scored') or 0), f('best_score')
            best = f"best score {b:.2f}" if b is not None else 'no score yet'
            cost = f" · Meta cost ${c:.2f}" if c is not None else ''
            emit(t, f"[{float(m.group(1)):6.1f} min] heartbeat · attempts scored {n:2d} · {best}{cost}",
                 dict(cost=round(c, 2) if c is not None else None, scored=n, best=b)); continue
        if s.startswith('[') and '] done {' in s: emit(t, s.split('] done {')[0] + '] done ...'); continue
        bold = s.startswith(('HARNESS', 'Agent:', 'ok', '> build')) or 'timeout gate OK' in s or 'BASELINE' in s or 'best_score' in s or 'attempts_scored' in s
        emit(t, (B if bold else '') + cut(s) + (G if bold else ''))
if skip['n']: emit(skip['t'], None)
rows = [r for r in rows if r[1] is not None]
if arg('--cost'):
    cs = json.load(open(arg('--cost')))
    for name, v in cs['by_model'].items():
        rows.append((rows[-1][0] + 0.5, f"{B}cost_summary.json: model {name} · {v['event_count']} billed events · Meta-reported ${float(v['reported_cost_usd']):.2f}{G}", dict(cost=round(float(v['reported_cost_usd']), 2))))
fh = open(arg('--jsonl'), 'w') if arg('--jsonl') else None
for t, text, meta in rows:
    line = f"{D}{int(t) // 3600}:{int(t) % 3600 // 60:02d}:{int(t) % 60:02d}{G}  {text}"; print(line)
    if fh: fh.write(json.dumps({'t': round(t, 2), 'line': line, 'meta': meta}) + '\n')
