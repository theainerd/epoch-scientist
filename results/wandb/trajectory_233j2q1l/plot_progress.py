"""Rebuild spark_trajectory_progress.png from history.jsonl (W&B export of run 233j2q1l). Usage: python plot_progress.py"""
import json, os
import matplotlib.pyplot as plt
here = os.path.dirname(os.path.abspath(__file__))
H = [json.loads(l) for l in open(os.path.join(here, 'history.jsonl'))]
H = [h for h in H if h.get('elapsed_min') is not None]
valid, lost, mf, mv = [], [], 0, 0  # W&B counters can step back briefly, so count only new highs
for h in H:
    f_, v_ = h['attempts_failed'], h['attempts_scored'] - h['attempts_failed']
    if f_ > mf: lost.append(h['elapsed_min']); mf = f_
    if v_ > mv and (h.get('last_score') or 0) > 0: valid.append((h['elapsed_min'], h['last_score'])); mv = v_
best = [(h['elapsed_min'], h['best_score']) for h in H if h.get('best_score') is not None]
FOC, GREY = '#2a7d4f', '#9aa3a0'
fig, ax = plt.subplots(figsize=(8.0, 3.8))
for s in ('top', 'right'): ax.spines[s].set_visible(False)
ax.axhline(100, color=GREY, lw=1, ls='--', zorder=1)
ax.text(178, 101.3, 'start program = 100 (by definition)', color='#5f6b66', fontsize=9, ha='right')
ax.step([b[0] for b in best], [b[1] for b in best], where='post', color=FOC, lw=2.2, zorder=3)
ax.scatter([v[0] for v in valid], [v[1] for v in valid], s=30, color=FOC, alpha=0.45, edgecolor='none', zorder=2, label=f'each scored attempt ({len(valid)})')
ax.scatter(lost, [92] * len(lost), marker='x', color='#b9504a', s=36, lw=1.6, zorder=2, label=f'attempt lost to a harness file-copy error ({len(lost)})')
ax.text(best[-1][0] + 1.5, best[-1][1], f'best {best[-1][1]:.1f}', color=FOC, fontsize=10, va='center', fontweight='bold')
ax.set_xlim(0, 182); ax.set_ylim(89, 146)
ax.set_xlabel('time since the run started (min)'); ax.set_ylabel('practice score (higher = better)')
ax.set_title(f'Open Muse Spark lifted the practice score from 100 to {best[-1][1]:.1f} in {H[-1]["elapsed_min"]:.0f} min', loc='left')
ax.legend(loc='center right', frameon=False, bbox_to_anchor=(1.0, 0.42))
fig.tight_layout(); fig.savefig(os.path.join(here, 'spark_trajectory_progress.png'), dpi=200)
print('scored', len(valid), 'lost', len(lost), 'best', round(best[-1][1], 2))
