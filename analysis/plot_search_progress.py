"""Search-progress figure for both blind runs, from results/*/ideas_table.csv -> media/stills/search_progress.png
Dev-set reference lines come from results/summary.csv (start program, expert solver, MILP)."""
import os, sys
import numpy as np, pandas as pd, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from paths import ROOT
R = os.path.join(ROOT, 'results')
a = pd.read_csv(os.path.join(R, 'aeossp', 'ideas_table.csv')); a['w'] = a.worker.str[-1].astype(int); a['k'] = a.groupby('w').cycle.rank().astype(int)
v = pd.read_csv(os.path.join(R, 'revisit', 'ideas_table.csv')); v['w'] = v.worker; v['k'] = v.cycle; v['score'] = v.harness_score
plt.rcParams.update({'font.size': 8, 'axes.spines.top': False, 'axes.spines.right': False, 'xtick.direction': 'out', 'ytick.direction': 'out'})
BLUE, GREY, INK = '#1f5fbf', '#8a8f98', '#111111'
fig, axs = plt.subplots(1, 2, figsize=(10, 3.9))
spec = [(axs[0], a, 'Photo scheduling (AEOSSP): 7 dev missions', 74.93, [('Expert solver MWIS', 77.40), ('MILP (best known)', 77.79)], (72.4, 78.2), None),
        (axs[1], v, 'Constellation design (Revisit): 4 dev missions', 69.82, [('Expert solver j2 set cover', 72.47)], (64, 79.5), 64.6)]
for ax, d, title, start, refs, yl, floor in spec:
    for w, c, lab, dx, dy in [(1, GREY, 'worker 1', -0.13, -0.35 if floor else 0), (2, BLUE, 'worker 2', 0.13, 0.1 if floor else 0)]:
        s = d[d.w == w].sort_values('k'); y = s.score.values
        low = (y < yl[0]) if floor else np.zeros(len(y), bool)
        ax.plot(s.k, np.where(low, np.nan, y), '-o', color=c, ms=4, lw=1.1, zorder=3)
        if low.any(): ax.plot(s.k[low] + dx, [floor] * low.sum(), 'v', color=c, ms=6, zorder=3, clip_on=False)
        ax.text(10.25, s.score.iloc[-1] + dy, lab, color=c, va='center', fontsize=7)
    best = [max([start] + list(d[d.k <= k].score)) for k in range(1, 11)]
    ax.step(range(1, 11), best, where='post', color=INK, lw=1.8, zorder=4)
    ax.text(1.05, best[-1] + .15, f'Muse best so far: {best[-1]:.2f}', fontsize=7, fontweight='bold', color=INK)
    ax.axhline(start, color='#555', lw=1); ax.text(0.6, start - .32, f'Simple start program {start:.2f}', fontsize=7, color='#555', va='top')
    for lab, val in refs:
        ax.axhline(val, color='#aaa', ls='--', lw=1); ax.text(0.6, val + .1, f'{lab} {val:.2f}', fontsize=7, color='#777', va='bottom')
    ax.set_ylim(*yl); ax.set_xlim(0.5, 11.6); ax.set_xticks(range(1, 11)); ax.set_title(title, loc='left')
    ax.set_xlabel('Attempt per worker (2 workers in parallel)')
axs[0].set_ylabel('Mean mission score (higher = better)')
axs[1].text(1.3, 64.6 + 0.9, '▼ broken attempt (score 0–45, off scale)', fontsize=7, color='#555')
fig.suptitle('Muse Wonder improves through its own loop: 3 of 4 first attempts were worse than the start program', x=0.01, ha='left', fontsize=9)
fig.tight_layout(); out = os.path.join(ROOT, 'media', 'stills', 'search_progress.png'); fig.savefig(out, dpi=300); print('->', out)
