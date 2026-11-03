"""Replay a recorded OpenCode agent log (JSON events written while Meta Muse Wonder worked) as a readable timeline.
Usage: python demo/replay_agent.py <agent_opencode_*.log> [--jsonl OUT.jsonl]
Every printed line comes from the log: file reads, Muse's plan (todo list), code edits (first lines of the new code),
shell commands and their output, reasoning-token counts and Muse's final message. Times are the real offsets in the log.
Token and cost totals are the values the Meta Model API reported per model call (step_finish events)."""
import json, sys, os
path = sys.argv[1]; out = sys.argv[sys.argv.index('--jsonl') + 1] if '--jsonl' in sys.argv else None
ev = [json.loads(l) for l in open(path) if l.startswith('{')]
T0 = min(e['timestamp'] for e in ev if 'timestamp' in e)
rows = []  # (seconds, text, meta)
calls = tok = 0; cost = 0.0
def short(p): return os.path.basename(p) if '/ideas/' in p or p.startswith('/kaggle') else p
def cut(x, n): return x if len(x) <= n else x[:n - 3] + '...'
def add(ms, text, meta=None): rows.append(((ms - T0) / 1000, text, meta))
B, D, G = '\033[1m', '\033[2m', '\033[0m'
for e in ev:
    ty, p = e.get('type'), e.get('part', {})
    if ty == 'step_finish':
        tk = p.get('tokens', {}); calls += 1; cost += p.get('cost', 0) or 0
        tok += tk.get('input', 0) + tk.get('output', 0) + tk.get('reasoning', 0) + tk.get('cache', {}).get('read', 0)
        if tk.get('reasoning', 0) >= 300:
            add(e['timestamp'], f"{D}think   {tk['reasoning']:,} reasoning tokens{G}", None)
        rows.append(((e['timestamp'] - T0) / 1000, None, dict(calls=calls, tokens=tok, cost=round(cost, 3))))
    elif ty == 'tool_use':
        st = p.get('state', {}); inp = st.get('input', {}); tool = p.get('tool'); tm = st.get('time', {})
        t1, t2 = tm.get('start', e['timestamp']), tm.get('end', e['timestamp'])
        if tool == 'read':
            add(t1, f"read    {short(inp.get('filePath', ''))}")
        elif tool == 'skill':
            add(t1, f"skill   {inp.get('name')}")
        elif tool in ('glob', 'grep'):
            add(t1, f"{tool:7s} {inp.get('pattern', '')}")
        elif tool == 'todowrite':
            todos = inp.get('todos', [])
            add(t1, f"{B}plan{G}    " + ' · '.join(('[x] ' if x['status'] == 'completed' else '[~] ' if x['status'] == 'in_progress' else '[ ] ') + x['content'] for x in todos))
        elif tool in ('edit', 'write'):
            new = (inp.get('newString') if tool == 'edit' else inp.get('content')) or ''; old = inp.get('oldString', '') if tool == 'edit' else ''
            nl = new.strip('\n').splitlines()
            add(t1, f"{B}{tool:7s} {short(inp.get('filePath', ''))}{G}  {D}({len(old.splitlines())} -> {len(nl)} lines){G}")
            if inp.get('filePath', '').endswith('.py'):
                for k, line in enumerate(nl[:3 if len(nl) < 40 else 6]): add(t1 + 1 + k, f"        {D}+ {cut(line, 96)}{G}")
        elif tool == 'bash':
            cmd = inp.get('command', '').replace('${TASK_PYTHON:-$WRAPPER_PYTHON} -I -m ', 'python -m ')
            add(t1, f"{B}bash    $ {cut(cmd, 160)}{G}")
            outp = [l for l in str(st.get('output', '')).splitlines() if l.strip() and not l.startswith(('evaluation outputs', 'evaluation runtime'))]
            for k, line in enumerate(outp[:12]): add(t2 + k, f"        {D}| {cut(line, 110)}{G}")
    elif ty == 'text':
        for k, line in enumerate(p.get('text', '').splitlines()):
            if line.strip(): add(e['timestamp'] + k, f"{B}muse{G}    {cut(line, 120)}" if k == 0 else f"        {cut(line, 120)}")
rows.sort(key=lambda r: r[0])
meta = None; fh = open(out, 'w') if out else None
print(f"{B}replay of {os.path.basename(path)} · model meta/muse-wonder-1.0 · OpenCode in AI-Scientist-v3{G}")
if fh: fh.write(json.dumps({'t': 0.0, 'line': f"{B}replay of {os.path.basename(path)} · model meta/muse-wonder-1.0 · OpenCode in AI-Scientist-v3{G}"}) + '\n')
for t, text, m in rows:
    if m: meta = m; continue
    mm, ss = divmod(int(t), 60); line = f"{D}[+{mm:02d}:{ss:02d}]{G} {text}"; print(line)
    if fh: fh.write(json.dumps({'t': round(t, 2), 'line': line, 'meta': meta}) + '\n')
print(f"{D}Meta Model API, as reported per call: {calls} calls · {tok:,} tokens · ${cost:.3f}{G}")
if fh: fh.write(json.dumps({'t': round(rows[-1][0] + 1, 2), 'line': f"{D}Meta Model API, as reported per call: {calls} calls · {tok:,} tokens · ${cost:.3f}{G}", 'meta': dict(calls=calls, tokens=tok, cost=round(cost, 3))}) + '\n'); fh.close()
