"""Animation: how Muse searched (AI-Scientist-v3 evolutionary loop), replayed from the real run records
(attempts_history.jsonl, idea folders, program hashes for parent links). Usage: python render_evo.py revisit|aeossp out.mp4 [--preview]"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import ROOT, AAB, WORK, ASSETS, FFMPEG, AEOSSP_PACK, REVISIT_DATA  # noqa: E402,F401
import json, sys, textwrap, math
from datetime import datetime, timezone
import numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.animation import FFMpegWriter
import viztemplate as V
plt.rcParams['animation.ffmpeg_path'] = FFMPEG
NAME, OUT = sys.argv[1], sys.argv[2]; PREVIEW = '--preview' in sys.argv
CFG = {'revisit': dict(family='Revisit Constellation', start=69.821, t0='2026-10-30T16:32:31', ylim=(67, 79.5), n_dev=4,
                       yard=[('benchmark solver', 72.474)], cross=('w1c4', 'w2c5', 'reuses worker 1\u2019s result'), minutes=105, cost=29.10,
                       end_rows=[('dev score', '69.8', '77.8'), ('satellites (4 dev missions)', '76', '57'), ('sealed missions: mean score', '67.4', '77.1')],
                       end_note='Sealed = 11 missions Muse never saw. The benchmark solver scores 72.5 on the dev missions.'),
       'aeossp': dict(family='Earth-observation scheduling (AEOSSP)', start=74.926, t0='2026-10-30T08:29:28', ylim=(72, 78.2), n_dev=7,
                      yard=[('benchmark greedy solver', 72.90), ('best published solver', 77.40)], cross=('w1c7', 'w2c8', 'adopts worker 1\u2019s pricing idea'),
                      minutes=113, cost=27.66,
                      end_rows=[('dev score', '74.9', '76.6'), ('test score (5 missions)', '73.3', '75.4'), ('sealed missions won', '', '23 / 23')],
                      end_note='The best published solver still scores higher on the test set (75.95).')}[NAME]
D = json.load(open(_os.path.join(ROOT, 'results', 'evo_runs.json')))[NAME]; LAB = json.load(open(_os.path.join(ROOT, 'results', 'labels.json')))[NAME]
t0 = datetime.fromisoformat(CFG['t0']).replace(tzinfo=timezone.utc)
for r in D:
    r['id'] = f"w{r['worker']}c{r['cycle']}"; r['min'] = (datetime.fromisoformat(r['t'].replace('Z', '+00:00')) - t0).total_seconds() / 60
    r['broke'] = r['n_valid'] < r['n_cases']
score_of = {r['id']: r['score'] for r in D}; score_of['start'] = CFG['start']
first_valid = {}
best = CFG['start']
for r in D:
    ps = score_of[r['parent_of']]
    if r['best_updated']:
        fv = r['worker'] not in first_valid; first_valid[r['worker']] = r['id']
        if fv and r['score'] < CFG['start']: r['verdict'] = ('KEPT as this worker\u2019s first fully valid program (still below the start)', V.MUSE)
        else: r['verdict'] = ('KEPT: better than its parent, so it becomes the new parent', V.MUSE)
    elif r['broke']: r['verdict'] = (f"DISCARDED: plan invalid on {r['n_cases'] - r['n_valid']} of {r['n_cases']} missions", V.ALARM)
    elif r['score'] < ps - 0.005: r['verdict'] = ('DISCARDED: worse than its parent', V.MUTED)
    else: r['verdict'] = ('DISCARDED: no gain over its parent', V.MUTED)
    if not r['broke'] and r['score'] > best + 1e-9: best = r['score']; r['newbest'] = True
    r['best_after'] = best
win = max((r for r in D if not r['broke']), key=lambda r: r['score']); path = []; cur = win['id']
while cur != 'start':
    path.append(cur); cur = next(r for r in D if r['id'] == cur)['parent_of']
path = path[::-1]
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': V.SMALL, 'text.color': V.TEXT, 'axes.labelcolor': V.MUTED, 'xtick.color': V.MUTED, 'ytick.color': V.MUTED, 'axes.edgecolor': V.FAINT})
fig = plt.figure(figsize=(19.2, 10.8), dpi=100, facecolor=V.BG); V.add_brand(fig)
# ---------------- loop explainer layer
LX = fig.add_axes([0, 0, 1, 1], zorder=30); LX.axis('off'); LX.set_xlim(0, 16); LX.set_ylim(0, 9); LX.add_patch(plt.Rectangle((0, 0), 16, 9, color=V.BG))
LX.text(0.35, 8.45, 'ASTROAGENTBENCH', fontsize=V.SMALL, color=V.MUSE, fontweight='bold'); LX.text(2.15, 8.45, CFG['family'] + '  \u00b7  how the search works', fontsize=V.SMALL, color=V.MUTED)
LX.text(0.35, 7.95, 'Muse improves the planner by evolution: change one thing, test it, keep it only if it is better', fontsize=V.BIG, fontweight='bold')
ST = [('1  Read memory', 'Lessons from every earlier attempt,\nincluding the other worker\u2019s.'),
      ('2  Propose one idea', 'A hypothesis, plus checks\nthat define success.'),
      ('3  Change the program', 'Muse edits a copy of its current\nbest program (the parent).'),
      ('4  Score it', 'The frozen AstroAgentBench verifier\nscores it on the development missions.'),
      ('5  Select', 'Valid and better: it becomes the new parent.\nOtherwise discard it, but keep the lesson.')]
CX, CY, RR = 8.0, 3.95, 2.75; ANG = [90 - i * 72 for i in range(5)]; BOX = []
LX.add_patch(plt.Circle((CX, CY), RR, fill=False, ec='#1f2a3d', lw=10))
for i, (a, (t, s)) in enumerate(zip(ANG, ST)):
    x, y = CX + RR * math.cos(math.radians(a)), CY + RR * math.sin(math.radians(a))
    b = FancyBboxPatch((x - 1.55, y - 0.42), 3.1, 0.84, boxstyle='round,pad=0.06', fc='#111a2a', ec='#26324a', lw=1.5, zorder=3); LX.add_patch(b)
    tt = LX.text(x, y, t, ha='center', va='center', fontsize=V.MID + 1, fontweight='bold', color=V.MUTED, zorder=4); BOX.append((b, tt, x, y))
LX.text(CX, CY + 0.25, '10 cycles per worker', ha='center', fontsize=V.MID + 2, fontweight='bold'); LX.text(CX, CY - 0.25, '2 workers in parallel', ha='center', fontsize=V.MID + 2, fontweight='bold')
LX.text(CX, CY - 0.75, 'no web  \u00b7  no papers  \u00b7  no reference code', ha='center', fontsize=V.SMALL + 1, color=V.MUTED)
DOT = LX.scatter([], [], s=0)
DESC = LX.text(CX, 0.95, '', ha='center', va='center', fontsize=V.MID + 2, color=V.TEXT, bbox=dict(boxstyle='round,pad=0.55', fc='#121b2c', ec='#26324a'))
def draw_loop(u):
    """u in [0, 5): station index + progress."""
    i = int(u) % 5; f = u - int(u)
    for j, (b, tt, x, y) in enumerate(BOX):
        on = j == i; b.set_edgecolor(V.MUSE if on else '#26324a'); b.set_facecolor('#132644' if on else '#111a2a'); tt.set_color(V.TEXT if on else V.MUTED)
    a0, a1 = ANG[i], ANG[i] - 72 * min(1, max(0, (f - 0.65) / 0.35)); a = math.radians(a1)
    DESC.set_text(ST[i][0][3:] + ':  ' + ST[i][1].replace('\n', ' '))
# ---------------- replay layer
fig.text(0.02, 0.962, 'ASTROAGENTBENCH', fontsize=V.SMALL, color=V.MUSE, fontweight='bold'); fig.text(0.128, 0.962, CFG['family'] + '  \u00b7  replay of the real run', fontsize=V.SMALL, color=V.MUTED)
fig.text(0.02, 0.918, '20 ideas, 2 workers: each new program starts from its worker\u2019s best so far', fontsize=V.BIG, fontweight='bold')
CLK = fig.text(0.98, 0.928, '', fontsize=V.BIG, fontweight='bold', ha='right', family='DejaVu Sans Mono'); SUB = fig.text(0.98, 0.962, '', fontsize=V.SMALL, ha='right', color=V.MUTED)
TX = fig.add_axes([0.035, 0.40, 0.60, 0.47]); TX.set_xlim(-0.8, 10.7); TX.set_ylim(-0.75, 1.75); TX.axis('off')
POS = {'start': (0, 0.5)}
for r in D: POS[r['id']] = (r['cycle'], 1.0 if r['worker'] == 1 else 0.0)
TX.add_patch(FancyBboxPatch((0.55, 0.38), 10.0, 0.24, boxstyle='round,pad=0.02', fc='#101a2b', ec='#22304a', zorder=0))
MEM = TX.text(5.55, 0.5, 'shared memory: a lesson from every attempt', ha='center', va='center', fontsize=V.SMALL, color=V.MUTED, zorder=1)
TX.text(-0.75, 1.0, 'Worker 1', va='center', fontsize=V.MID, fontweight='bold'); TX.text(-0.75, 0.0, 'Worker 2', va='center', fontsize=V.MID, fontweight='bold')
for c in range(1, 11): TX.text(c, 1.62, f'{c}', ha='center', fontsize=V.SMALL, color=V.FAINT)
TX.text(5.5, 1.75, 'cycle', ha='center', fontsize=V.SMALL, color=V.FAINT)
TX.scatter([0], [0.5], s=420, color=V.BASE, zorder=5, edgecolors=V.BG)
TX.text(-0.22, 0.5, f"start\n{CFG['start']:.1f}", ha='right', va='center', fontsize=V.SMALL, color=V.BASE, linespacing=1.2)
ART = {}
for r in D:
    (x, y), (px, py) = POS[r['id']], POS[r['parent_of']]
    dx = x - px; rad = (0.6 / dx) * (1 if r['worker'] == 1 else -1) if (py == y and dx > 1) else 0.0
    e = FancyArrowPatch((px, py), (x, y), connectionstyle=f'arc3,rad={rad}', arrowstyle='-', color=V.MUSE if r['best_updated'] else V.FAINT,
                        lw=2.2 if r['best_updated'] else 1.0, ls='-' if r['best_updated'] else (0, (3, 3)), zorder=2, visible=False, shrinkA=9, shrinkB=9); TX.add_patch(e)
    if r['broke']: n = TX.scatter([x], [y], s=300, marker='X', color=V.ALARM, zorder=5, visible=False)
    elif r['best_updated']: n = TX.scatter([x], [y], s=420, color=V.MUSE, edgecolors='white', lw=1.5, zorder=5, visible=False)
    else: n = TX.scatter([x], [y], s=380, facecolors=V.BG, edgecolors=V.MUTED, lw=1.6, zorder=5, visible=False)
    lab = TX.text(x, y + (0.2 if r['worker'] == 1 else -0.3), f"{r['score']:.1f}", ha='center', fontsize=V.SMALL, color=V.MUSE if r['best_updated'] else (V.ALARM if r['broke'] else V.MUTED), visible=False, zorder=6)
    ART[r['id']] = (e, n, lab)
RING = TX.scatter([], [], s=900, facecolors='none', edgecolors='white', lw=2.0, zorder=7)
PULSE = TX.scatter([], [], s=90, color=V.MUSE, zorder=8)
ca, cb, ct = CFG['cross']; (ax_, ay_), (bx_, by_) = POS[ca], POS[cb]
CROSS = FancyArrowPatch((ax_ + 0.1, ay_ - 0.12), (bx_ - 0.12, by_ + 0.12), connectionstyle='arc3,rad=-0.25', arrowstyle='-|>', mutation_scale=18, color='#f5a524', lw=1.8, ls='--', zorder=4, visible=False)
TX.add_patch(CROSS); CROSST = TX.text((ax_ + bx_) / 2 + 0.25, 0.73, ct, fontsize=V.SMALL, color='#f5a524', fontweight='bold', visible=False, zorder=9)
WIN, = TX.plot([], [], color='#ffffff', lw=4.5, alpha=0.35, zorder=1)
# idea card
CA = fig.add_axes([0.655, 0.40, 0.325, 0.47]); CA.axis('off'); CA.set_xlim(0, 1); CA.set_ylim(0, 1)
CA.add_patch(FancyBboxPatch((0.01, 0.01), 0.98, 0.98, boxstyle='round,pad=0.01', fc='#0f1828', ec='#26324a'))
C_HEAD = CA.text(0.06, 0.9, '', fontsize=V.SMALL + 1, color=V.MUSE, fontweight='bold'); CA.text(0.06, 0.81, 'IDEA (plain-language summary)', fontsize=V.SMALL - 1, color=V.FAINT)
C_TXT = CA.text(0.06, 0.76, '', fontsize=V.MID + 4, fontweight='bold', va='top', linespacing=1.35)
C_PAR = CA.text(0.06, 0.40, '', fontsize=V.SMALL + 1, color=V.MUTED)
C_SC = CA.text(0.06, 0.28, '', fontsize=V.MID + 2, fontweight='bold')
C_VER = CA.text(0.06, 0.205, '', fontsize=V.SMALL + 1, fontweight='bold', va='top', linespacing=1.3)
C_LES = CA.text(0.06, 0.045, '', fontsize=V.SMALL, color=V.FAINT)
# best-so-far chart
BX = fig.add_axes([0.06, 0.085, 0.79, 0.22]); BX.set_facecolor(V.BG)
for s in ('top', 'right'): BX.spines[s].set_visible(False)
lo, hi = CFG['ylim']; BX.set_xlim(0, 20.5); BX.set_ylim(lo, hi); BX.set_xticks(range(0, 21, 2)); BX.set_xlabel('attempt number', fontsize=V.SMALL)
BX.set_title('Best valid dev score so far', loc='left', fontsize=V.MID, pad=8); BX.grid(axis='y', color='#1a2334', lw=0.6)
BX.axhline(CFG['start'], color=V.BASE, lw=1.2, ls=':'); BX.text(20.45, CFG['start'], ' start', va='center', fontsize=V.SMALL, color=V.BASE)
for nm, v in CFG['yard']:
    BX.axhline(v, color='#f5a524', lw=1.2, ls='--'); BX.text(20.45, v, ' ' + nm, va='center', fontsize=V.SMALL, color='#f5a524')
BEST, = BX.step([], [], where='post', color=V.MUSE, lw=2.8)
PTS = BX.scatter([], [], s=40, zorder=5)
BELOW = BX.text(10.3, lo + 0.45, f'dots on the bottom edge: score below {lo:.0f}', fontsize=V.SMALL - 1, color=V.FAINT, visible=False)
CARDX = fig.add_axes([0, 0, 1, 1], zorder=50); CARDX.axis('off'); CARDX.set_xlim(0, 1); CARDX.set_ylim(0, 1); CARDX.add_patch(plt.Rectangle((0, 0), 1, 1, color=V.BG)); CARD_ITEMS = []
def card(title, sub, rows=None, notes=()):
    for it in CARD_ITEMS: it.remove()
    CARD_ITEMS.clear(); add = CARD_ITEMS.append
    add(CARDX.text(0.5, 0.86, 'ASTROAGENTBENCH', ha='center', fontsize=V.MID, color=V.MUSE, fontweight='bold'))
    add(CARDX.text(0.5, 0.80, title, ha='center', fontsize=V.BIG + 8, fontweight='bold'))
    add(CARDX.text(0.5, 0.74, sub, ha='center', va='top', fontsize=V.MID + 3, color=V.MUTED, linespacing=1.6))
    if rows:
        for j, (lab, a, b) in enumerate(rows):
            cx = 0.5 + (j - (len(rows) - 1) / 2) * 0.30
            add(CARDX.add_patch(FancyBboxPatch((cx - 0.13, 0.33), 0.26, 0.22, boxstyle='round,pad=0.01', fc='#111a2a', ec='#26324a')))
            add(CARDX.text(cx, 0.51, lab, ha='center', fontsize=V.MID, color=V.MUTED))
            if a:
                add(CARDX.text(cx - 0.065, 0.41, a, ha='center', fontsize=V.KPI + 6, fontweight='bold', color=V.BASE)); add(CARDX.text(cx, 0.41, '\u2192', ha='center', fontsize=V.KPI, color=V.FAINT))
                add(CARDX.text(cx + 0.065, 0.41, b, ha='center', fontsize=V.KPI + 6, fontweight='bold', color=V.MUSE))
            else: add(CARDX.text(cx, 0.41, b, ha='center', fontsize=V.KPI + 6, fontweight='bold', color=V.MUSE))
    y0 = 0.25 if rows else 0.55
    for i, n in enumerate(notes): add(CARDX.text(0.5, y0 - i * 0.055, n, ha='center', fontsize=V.MID + 1, color=V.TEXT if i == 0 else V.MUTED))
    CARDX.set_visible(True)
def draw_replay(k, f):
    """k attempts fully shown (0..20), f in [0,1] progress of attempt k (index k) appearing."""
    shown = D[:k + (1 if f > 0 else 0)]; r = shown[-1] if shown else None
    for i, q in enumerate(D):
        vis = i < len(shown); e, n, lab = ART[q['id']]; e.set_visible(vis); n.set_visible(vis); lab.set_visible(vis)
    if r is not None:
        x, y = POS[r['id']]; RING.set_offsets([[x, y]])
        g = min(1, f * 2.5) if f > 0 else 1; PULSE.set_offsets([[x, y + (0.5 - y) * g]] if 0 < f < 0.6 else np.zeros((0, 2)))
        C_HEAD.set_text(f"WORKER {r['worker']}  \u00b7  CYCLE {r['cycle']}"); C_TXT.set_text(textwrap.fill(LAB[r['id']], 26))
        C_PAR.set_text('starts from: ' + ('the start program' if r['parent_of'] == 'start' else 'cycle ' + r['parent_of'].split('c')[1] + ' program of this worker'))
        C_SC.set_text(f"dev score {r['score']:.2f}" + ('   new overall best' if r.get('newbest') else '')); C_SC.set_color(V.MUSE if r['best_updated'] else (V.ALARM if r['broke'] else V.TEXT))
        C_VER.set_text(textwrap.fill(r['verdict'][0], 40)); C_VER.set_color(r['verdict'][1]); C_LES.set_text('lesson written to shared memory')
        CLK.set_text(f"attempt {len(shown)} of 20"); SUB.set_text(f"about {r['min']:.0f} min into the run")
        cross_on = any(q['id'] == cb for q in shown); CROSS.set_visible(cross_on); CROSST.set_visible(cross_on)
    else:
        RING.set_offsets(np.zeros((0, 2))); PULSE.set_offsets(np.zeros((0, 2))); CLK.set_text('attempt 0 of 20'); SUB.set_text('')
        C_HEAD.set_text(''); C_TXT.set_text('Both workers start from\nthe same simple program.'); C_PAR.set_text(''); C_SC.set_text(f"dev score {CFG['start']:.2f}"); C_SC.set_color(V.BASE); C_VER.set_text(''); C_LES.set_text('')
        CROSS.set_visible(False); CROSST.set_visible(False)
    xs = [0] + [i + 1 for i in range(len(shown))]; ys = [CFG['start']] + [q['best_after'] for q in shown]; BEST.set_data(xs, ys)
    if shown:
        PTS.set_offsets([[i + 1, max(min(q['score'], hi - 0.1), lo + 0.15)] for i, q in enumerate(shown)]); BELOW.set_visible(any(q['score'] < lo for q in shown))
        PTS.set_color([V.MUSE if q['best_updated'] else (V.ALARM if q['broke'] else V.MUTED) for q in shown]); PTS.set_sizes([60 if q['best_updated'] else 34 for q in shown])
    else: PTS.set_offsets(np.zeros((0, 2)))
def show_winner():
    pts = [POS['start']] + [POS[p] for p in path]; WIN.set_data([p[0] for p in pts], [p[1] for p in pts])
FPS = 30; T_TITLE, T_ST, T_ATT, T_HOLD, T_END = 4.5, 3.6, 2.1, 3.0, 9.0
def title():
    card('How Muse searched for a better planner', f"{CFG['family']}  \u00b7  replay of the real run ({CFG['minutes']} min, ${CFG['cost']:.2f} of model use)",
         notes=('Two workers run the same loop in parallel, 10 cycles each.', 'Every number below comes from the run records and the frozen verifier.'))
def outro():
    steps = ' \u2192 '.join(['start'] + ['c' + p.split('c')[1] for p in path])
    card('Result of the search', f"Winning lineage (worker {win['worker']}):  {steps}",
         rows=CFG['end_rows'], notes=(f"Best program: \u201c{LAB[win['id']]}\u201d, built on {len(path) - 1} earlier kept changes.", CFG['end_note']))
if PREVIEW:
    title(); fig.savefig(OUT.replace('.mp4', '_title.png'), facecolor=V.BG); CARDX.set_visible(False)
    LX.set_visible(True); draw_loop(2.3); fig.savefig(OUT.replace('.mp4', '_loop.png'), facecolor=V.BG); LX.set_visible(False)
    for k in (5, 14, 19):
        draw_replay(k, 0.9); fig.savefig(OUT.replace('.mp4', f'_k{k}.png'), facecolor=V.BG)
    show_winner(); fig.savefig(OUT.replace('.mp4', '_win.png'), facecolor=V.BG); outro(); fig.savefig(OUT.replace('.mp4', '_end.png'), facecolor=V.BG); sys.exit()
w = FFMpegWriter(fps=FPS, bitrate=6000, codec='libx264', extra_args=['-pix_fmt', 'yuv420p'])
with w.saving(fig, OUT, dpi=100):
    draw_replay(0, 0); title()
    for _ in range(int(T_TITLE * FPS)): w.grab_frame(facecolor=V.BG)
    CARDX.set_visible(False); LX.set_visible(True)
    for i in range(int(5 * T_ST * FPS)): draw_loop(i / (T_ST * FPS)); w.grab_frame(facecolor=V.BG)
    LX.set_visible(False)
    for _ in range(int(1.5 * FPS)): w.grab_frame(facecolor=V.BG)
    for k in range(20):
        n = int(T_ATT * FPS)
        for i in range(n): draw_replay(k, (i + 1) / n); w.grab_frame(facecolor=V.BG)
    draw_replay(20, 0); show_winner()
    for _ in range(int(T_HOLD * FPS)): w.grab_frame(facecolor=V.BG)
    outro()
    for _ in range(int(T_END * FPS)): w.grab_frame(facecolor=V.BG)
print('wrote', OUT)
