"""Redraw the W&B run charts from results/wandb/*/history.jsonl -> media/stills/wandb_runs.png"""
import os, sys, json
import pandas as pd, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from paths import ROOT
plt.rcParams.update({'font.size': 8, 'axes.spines.top': False, 'axes.spines.right': False, 'axes.titlesize': 8.5})
RUNS = [('aeossp', 'bcw9vydb', 'Photo scheduling (AEOSSP)', 'aeossp-blind-muse-wonder-1.0-1030-0829', 72, 77.2),
        ('revisit', 'z3vvh4ce', 'Constellation design (Revisit)', 'revisit-blind-muse-wonder-1.0-1030-1632', 60, 79)]
BLUE, GREY = '#1f5fbf', '#8a8f98'
fig, axs = plt.subplots(2, 2, figsize=(10, 6.2), gridspec_kw={'height_ratios': [2, 1]})
for j, (s, rid, title, name, lo, hi) in enumerate(RUNS):
    f = os.path.join(ROOT, 'results', 'wandb', f'{s}_{rid}', 'history.jsonl')
    h = pd.DataFrame([json.loads(l) for l in open(f) if l.strip()]).sort_values('_step'); t = h.elapsed_min
    ax = axs[0, j]
    ax.plot(t, h.best_score, color=BLUE, lw=2, drawstyle='steps-post', label='best_score')
    ax.plot(t, h.last_score, 'o-', color=GREY, ms=3, lw=1, label='last_score')
    low = h.last_score < lo
    if low.any(): ax.plot(t[low], [lo + 0.3] * low.sum(), 'v', color=GREY, ms=6)
    ax.set_ylim(lo, hi); ax.set_title(f'{title}\nW&B run {name}', loc='left')
    ax.text(t.iloc[-1], h.best_score.iloc[-1] + 0.15, f'{h.best_score.iloc[-1]:.2f}', color=BLUE, ha='right', va='bottom', fontsize=7, fontweight='bold')
    ax2 = axs[1, j]
    ax2.plot(t, h.attempts_scored, color=BLUE, lw=1.5, drawstyle='steps-post', label='attempts_scored')
    ax2.plot(t, h.attempts_failed, color='#c0392b', lw=1.2, drawstyle='steps-post', label='attempts_failed')
    ax2.set_xlabel('elapsed_min'); ax2.set_ylim(-1, 21)
axs[0, 0].set_ylabel('dev score (higher = better)'); axs[1, 0].set_ylabel('attempts')
axs[0, 0].legend(loc='lower right', frameon=False); axs[1, 0].legend(loc='center right', frameon=False)
axs[0, 1].text(0.02, 0.04, '▼ attempt scored below the axis (broken plan)', transform=axs[0, 1].transAxes, fontsize=7, color='#555')
fig.suptitle('Weights & Biases run logs, redrawn from the exported history (results/wandb/)', x=0.01, ha='left', fontsize=9)
fig.tight_layout(); out = os.path.join(ROOT, 'media', 'stills', 'wandb_runs.png'); fig.savefig(out, dpi=250); print('->', out)
