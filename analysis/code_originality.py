"""Code-originality check: did Muse write its own code, or recall the benchmark's public reference solvers?

For each Muse program we count the fraction of its 20-token code sequences that also occur in the reference solvers of the
same problem. Comments are dropped, and strings, numbers and all non-builtin names are replaced by placeholders, so renamed
copies are still caught. Two controls: solvers of an unrelated problem (noise floor) and a reference solver file with all
names renamed (positive control, should be ~100%).
Usage: python analysis/code_originality.py      (needs `make fetch`)   -> results/code_originality.csv
"""
import os, sys, io, re, glob, csv, keyword, builtins, tokenize
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from paths import ROOT, AAB

K = 20
KEEP = set(keyword.kwlist) | set(dir(builtins))
SKIP = {tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.ENCODING, tokenize.ENDMARKER}

def tokens(src):
    out = []
    for t in tokenize.generate_tokens(io.StringIO(src).readline):
        if t.type in SKIP: continue
        if t.type == tokenize.STRING: out.append('STR')
        elif t.type == tokenize.NUMBER: out.append('NUM')
        elif t.string.isidentifier() and t.string not in KEEP: out.append('ID')
        else: out.append(t.string)
    return out

def grams(src): tk = tokens(src); return {tuple(tk[i:i + K]) for i in range(len(tk) - K + 1)}
def read(f): return open(f, errors='ignore').read()
def corpus(family):
    files = glob.glob(os.path.join(AAB, 'solvers', family, '**', '*.py'), recursive=True)
    assert files, f'no reference solvers for {family} under {AAB}/solvers (run make fetch)'
    return set().union(*(grams(read(f)) for f in files)), files

ref = {p: corpus(f) for p, f in [('aeossp', 'aeossp_standard'), ('revisit', 'revisit_constellation')]}
other = {'aeossp': 'revisit', 'revisit': 'aeossp'}
programs = [('aeossp', 'best (w2 cycle 8)', 'results/aeossp/programs/best_w2_cycle8.py'),
            ('aeossp', 'w1 best (cycle 10)', 'results/aeossp/programs/best_w1_cycle10.py'),
            ('revisit', 'best (w2 cycle 10)', 'results/revisit/programs/best_w2_cycle10.py'),
            ('revisit', 'runner-up (w1 cycle 8)', 'results/revisit/programs/runner_up_w1_cycle8.py')]
rows = []
for p, name, rel in programs:
    src = read(os.path.join(ROOT, rel)); g = grams(src)
    rows.append(dict(problem=p, program=name, lines=src.count('\n') + 1,
                     overlap_same_problem_solvers=round(len(g & ref[p][0]) / len(g), 4),
                     overlap_unrelated_solvers_noise_floor=round(len(g & ref[other[p]][0]) / len(g), 4)))
# positive control: the largest Revisit reference file with every long name renamed
ctrl = max(ref['revisit'][1], key=os.path.getsize)
renamed = re.sub(r'\b([a-z_][a-z0-9_]{3,})\b', lambda m: m.group(1) if m.group(1) in KEEP else 'v_' + m.group(1)[::-1], read(ctrl))
g = grams(renamed)
rows.append(dict(problem='revisit', program='CONTROL: renamed copy of a reference solver', lines=renamed.count('\n') + 1,
                 overlap_same_problem_solvers=round(len(g & ref['revisit'][0]) / len(g), 4), overlap_unrelated_solvers_noise_floor=''))
out = os.path.join(ROOT, 'results', 'code_originality.csv')
with open(out, 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
for r in rows: print(r)
print('->', out)
