"""Re-flatten both official verifiers from the AstroAgentBench checkout and check that they are byte-identical to the frozen
copies in tasks/ (the evaluators pin them by SHA-256)."""
import os, sys, hashlib, subprocess
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from paths import ROOT, WORK
h = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
ok = True
for script, frozen, made in (('flatten_aeossp_verifier.py', 'tasks/aeossp/aab_verifier.py', 'aab_verifier.py'), ('flatten_revisit_verifier.py', 'tasks/revisit/revisit_verifier.py', 'revisit_verifier.py')):
    subprocess.run([sys.executable, os.path.join(ROOT, 'data', script)], check=True, capture_output=True)
    a, b = h(os.path.join(ROOT, frozen)), h(os.path.join(WORK, 'flatten', made)); ok &= a == b
    print(f'{frozen}: {"IDENTICAL" if a == b else "DIFFERENT"} ({a[:12]})')
sys.exit(0 if ok else 1)
