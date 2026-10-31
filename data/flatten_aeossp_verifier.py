"""Merge aab_verifier/{models,io,engine}.py into one module with identical code (relative imports removed)."""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import ROOT, AAB, WORK, ASSETS, FFMPEG, AEOSSP_PACK, REVISIT_DATA  # noqa: E402,F401
import re, ast
src = _os.path.join(AAB, 'benchmarks/aeossp_standard/verifier') + '/'
parts, names = [], {}
for f in ['models.py', 'io.py', 'engine.py']:
    s = open(src + f).read()
    s = s.replace('from __future__ import annotations\n', '')
    s = re.sub(r'^from \.\w+ import \([^)]*\)\n', '', s, flags=re.M)      # multi-line relative imports
    s = re.sub(r'^from \.\w+ import [^\n(]+\n', '', s, flags=re.M)        # single-line relative imports
    assert 'from .' not in s, f
    for node in ast.parse(s).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) or (isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)):
            n = node.name if hasattr(node, 'name') else node.targets[0].id
            names.setdefault(n, []).append(f)
    parts.append(f'# ===== from aab_verifier/{f} (unchanged) =====\n' + s)
dups = {k: v for k, v in names.items() if len(v) > 1}
print('duplicate top-level names:', dups)
out = '"""Frozen official AEOSSP verifier (AstroAgentBench benchmarks/aeossp_standard/verifier), merged into one file."""\nfrom __future__ import annotations\n' + '\n'.join(parts)
open(_os.path.join(_os.makedirs(_os.path.join(WORK, 'flatten'), exist_ok=True) or _os.path.join(WORK, 'flatten'), 'aab_verifier.py'), 'w').write(out); print('lines', out.count('\n'))
