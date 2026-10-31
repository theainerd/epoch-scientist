"""Revisit Constellation before/after video, redesigned (declutter + focus). Data: replay_train7.json (exported with exact
verifier physics by export_revisit.py and checked against the official verifier output)."""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import ROOT, AAB, WORK, ASSETS, FFMPEG, AEOSSP_PACK, REVISIT_DATA  # noqa: E402,F401
import json, sys, bisect
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.animation import FFMpegWriter
import matplotlib.pyplot as plt
import viztemplate as V
plt.rcParams['animation.ffmpeg_path'] = FFMPEG
R = json.load(open(_os.path.join(WORK, 'viz', 'revisit', 'replay_train7.json'))); OUT = sys.argv[1]; PREVIEW = '--preview' in sys.argv
FT = np.array(R['frame_t']); NT = len(R['targets']); REQ = np.array([t['req_h'] for t in R['targets']]) * 3600
TLAT = np.array([t['lat'] for t in R['targets']]); TLON = np.array([t['lon'] for t in R['targets']]); FPS = 30
KEY = {'base': 'start', 'muse': 'muse'}
S = {}
for k, rk in KEY.items():
    s = R[rk]; mids = [[] for _ in range(NT)]
    for p in s['photos']: mids[p['tgt']].append(p['mid'])
    mids = [sorted(m) for m in mids]
    def state(t, mids=mids):
        since = np.empty(NT); missed = np.zeros(NT, bool)
        for j, m in enumerate(mids):
            i = bisect.bisect_right(m, t); since[j] = t - (m[i - 1] if i else 0.0)
            pts = [0.0] + m[:i] + [t]; missed[j] = max(b - a for a, b in zip(pts, pts[1:])) > REQ[j] + 1e-9
        return since, missed
    lw = np.array([state(t)[0].max() / 3600 for t in FT])
    S[k] = dict(lat=np.array(s['lat']), lon=np.array(s['lon']), state=state, lw=lw, n=s['n_sat'], score=s['score'], miss=s['n_missing'],
                worst=s['worst_gap_h'], L=s['layout'], pm=np.array(sorted(p['mid'] for p in s['photos'])), pt=np.array([p['tgt'] for p in sorted(s['photos'], key=lambda p: p['mid'])]))
never = sorted(set(range(NT)) - {p['tgt'] for p in R['start']['photos']})
F = V.frame('Revisit Constellation  ·  sealed mission (never seen by Muse)  ·  31 places  ·  48 hours',
            'Muse meets every 8-hour deadline with half the satellites',
            ('satellites', 'places on time', 'longest wait now'), 'Longest time any place has waited for its next photo (hours)')
fig = F['fig']; A = {}
for k, ax in F['map'].items():
    L = S[k]['L']
    ax.text(0.012, 0.975, f"{S[k]['n']} satellites  ·  {L['planes']} orbit planes  ·  tilt {L['inc_deg']:.0f}\u00b0  ·  {L['alt_km']} km",
            transform=ax.transAxes, va='top', fontsize=V.SMALL, color=V.TEXT, bbox=dict(boxstyle='round,pad=0.35', fc='#0b1220e0', ec='none'), zorder=8)
    tr = LineCollection([], colors=[(0.75, 0.8, 0.88, 0.28)], lw=0.8, zorder=2); ax.add_collection(tr)
    tg = ax.scatter(TLON, TLAT, s=np.full(NT, 46.0), c=V.TEXT, edgecolors=V.BG, lw=0.8, zorder=4)
    ring = ax.scatter([], [], s=260, facecolors='none', edgecolors=V.COL[k], lw=2.0, zorder=5)
    sat = ax.scatter(np.zeros(S[k]['n']), np.zeros(S[k]['n']), s=30, c=V.COL[k], marker='D', edgecolors=V.BG, lw=0.6, zorder=6)
    A[k] = dict(ax=ax, tr=tr, tg=tg, ring=ring, sat=sat)
an = F['map']['base'].annotate('Never photographed:\ntoo far north for the\nbaseline\u2019s 55\u00b0 orbits', (TLON[never[0]], TLAT[never[0]]),
                               xytext=(TLON[never[0]] + 32, TLAT[never[0]] - 26), fontsize=V.MID, color=V.ALARM, fontweight='bold', zorder=9,
                               arrowprops=dict(arrowstyle='-|>', color=V.ALARM, lw=1.8), bbox=dict(boxstyle='round,pad=0.4', fc='#0b1220ee', ec=V.ALARM)) if never else None
ch = F['chart']; YM = 50; ch.set_xlim(0, 48); ch.set_ylim(0, YM); ch.set_xticks(range(0, 49, 6)); ch.set_yticks([0, 8, 24, 48])
ch.set_xlabel('mission time (hours)', fontsize=V.SMALL); ch.grid(axis='y', color='#1a2334', lw=0.6)
ch.axhline(8, color=V.ALARM, lw=1.4, ls='--'); ch.text(0.3, 9.5, '8-hour limit', fontsize=V.SMALL, color=V.ALARM)
CL = {k: ch.plot([], [], color=V.COL[k], lw=2.6 if k == 'muse' else 2.0)[0] for k in S}
EL = {k: ch.text(0, 0, '', fontsize=V.SMALL, color=V.COL[k], fontweight='bold', va='center') for k in S}
first_over = float(FT[np.argmax(S['base']['lw'] > 8)]) if (S['base']['lw'] > 8).any() else 1e9
BEATS = [(0, 'Each of the 31 places must be photographed again at least every 8 hours.'),
         (5 * 3600, f"Baseline: {S['base']['n']} satellites at a {S['base']['L']['inc_deg']:.0f}\u00b0 tilt.   Muse: {S['muse']['n']} satellites in near-polar orbits ({S['muse']['L']['inc_deg']:.0f}\u00b0), which pass over every latitude."),
         (first_over, f'Hour {first_over / 3600:.0f}: the baseline misses its first deadline. One place is never photographed.'),
         (20 * 3600, f"Muse spaces its photos evenly: no place waits longer than {S['muse']['worst']:.1f} hours."),
         (40 * 3600, f"Baseline: {NT - S['base']['miss']} of {NT} places on time.   Muse: {NT - S['muse']['miss']} of {NT}, with {S['base']['n'] - S['muse']['n']} fewer satellites.")]
def segs(lon, lat):
    out = []
    for a in range(len(lon)):
        s = np.column_stack([lon[a], lat[a]]); cut = np.where(np.abs(np.diff(s[:, 0])) > 180)[0] + 1
        out += [p for p in np.split(s, cut) if len(p) > 1]
    return out
def draw(fi):
    t = FT[fi]; F['clock'].set_text(f'hour {t / 3600:4.1f} of 48'); F['speed'].set_text('replay: 1 hour per second')
    for k, a in A.items():
        s = S[k]; since, missed = s['state'](t); over = since > REQ
        a['tg'].set_facecolors(np.where(over, V.ALARM, '#d5dbe4')); a['tg'].set_sizes(np.where(over, 120.0, 46.0))
        a['sat'].set_offsets(np.column_stack([s['lon'][:, fi], s['lat'][:, fi]]))
        a['tr'].set_segments(segs(s['lon'][:, max(0, fi - 12):fi + 1], s['lat'][:, max(0, fi - 12):fi + 1]))
        rec = s['pt'][(s['pm'] > t - 360) & (s['pm'] <= t)]; a['ring'].set_offsets(np.column_stack([TLON[rec], TLAT[rec]]) if len(rec) else np.zeros((0, 2)))
        k1, k2, k3 = F['kpi'][k]; ontime = NT - int(missed.sum()); w = since.max() / 3600
        k1.set_text(f"{s['n']}"); k2.set_text(f'{ontime} / {NT}'); k2.set_color(V.ALARM if ontime < NT else V.COL[k])
        k3.set_text(f'{w:.1f} h'); k3.set_color(V.ALARM if w > 8 else V.COL[k])
        CL[k].set_data(FT[:fi + 1] / 3600, s['lw'][:fi + 1]); EL[k].set_position((t / 3600 + 0.4, s['lw'][fi])); EL[k].set_text(V.TAG[k].lower() if fi > 20 else '')
    if an is not None: an.set_visible(t >= first_over)
    F['caption'].set_text(V.beat(BEATS, t))
def intro():
    V.show_card(F, 'Revisit Constellation',
                'Design a satellite constellation that photographs 31 places\nat least once every 8 hours, for 48 hours, with as few satellites as possible (maximum 20).',
                notes=('BEFORE: a simple baseline planner (evenly spread satellites at a 55\u00b0 tilt).',
                       'AFTER: the planner Muse discovered on its own, from only the problem, a simulator and a scorer.',
                       'This mission was sealed: Muse never saw it.'))
def outro():
    b, m = S['base'], S['muse']
    V.show_card(F, 'Result on the sealed mission', 'Official AstroAgentBench verifier',
                rows=[('satellites', f"{b['n']}", f"{m['n']}", True), ('places on time', f"{NT - b['miss']}/{NT}", f"{NT - m['miss']}/{NT}", True),
                      ('score (0-100)', f"{b['score']:.1f}", f"{m['score']:.1f}", True)],
                notes=('The benchmark\u2019s own solver needs 15 satellites on this mission.',
                       'Across all 11 sealed missions: mean score 67.4 \u2192 77.1. Muse still misses some deadlines on 2 of the 11.'))
if PREVIEW:
    for fi in (0, 400, 720, 1100, len(FT) - 1):
        draw(fi); fig.savefig(OUT.replace('.mp4', f'_f{fi}.png'), facecolor=V.BG)
    intro(); fig.savefig(OUT.replace('.mp4', '_intro.png'), facecolor=V.BG); outro(); fig.savefig(OUT.replace('.mp4', '_end.png'), facecolor=V.BG); sys.exit()
w = FFMpegWriter(fps=FPS, bitrate=7000, codec='libx264', extra_args=['-pix_fmt', 'yuv420p'])
with w.saving(fig, OUT, dpi=100):
    draw(0); intro()
    for _ in range(6 * FPS): w.grab_frame(facecolor=V.BG)
    V.hide_card(F)
    for fi in range(len(FT)): draw(fi); w.grab_frame(facecolor=V.BG)
    for _ in range(1 * FPS): w.grab_frame(facecolor=V.BG)
    outro()
    for _ in range(8 * FPS): w.grab_frame(facecolor=V.BG)
print('wrote', OUT)
