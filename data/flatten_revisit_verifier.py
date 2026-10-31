import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import ROOT, AAB, WORK, ASSETS, FFMPEG, AEOSSP_PACK, REVISIT_DATA  # noqa: E402,F401
import re, ast
src = _os.path.join(AAB, 'benchmarks/revisit_constellation/verifier') + '/'
parts, names = [], {}
for f in ['models.py', 'io.py', 'engine.py']:
    s = open(src + f).read().replace('from __future__ import annotations\n', '')
    s = re.sub(r'^from \.\w+ import \([^)]*\)\n', '', s, flags=re.M); s = re.sub(r'^from \.\w+ import [^\n(]+\n', '', s, flags=re.M)
    assert 'from .' not in s, f
    for node in ast.parse(s).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) or (isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)):
            n = node.name if hasattr(node, 'name') else node.targets[0].id; names.setdefault(n, []).append(f)
    parts.append(f'# ===== from revisit_constellation/verifier/{f} (unchanged) =====\n' + s)
print('duplicate names:', {k: v for k, v in names.items() if len(v) > 1})
open(_os.path.join(_os.makedirs(_os.path.join(WORK, 'flatten'), exist_ok=True) or _os.path.join(WORK, 'flatten'), 'revisit_verifier.py'), 'w').write('"""Frozen official AstroAgentBench revisit_constellation verifier, merged into one file (code unchanged)."""\nfrom __future__ import annotations\n' + '\n'.join(parts))
