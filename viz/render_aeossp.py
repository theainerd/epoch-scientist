"""AEOSSP before/after video, redesigned (declutter + focus). Data: viz3d/app/data/replay.json + mission.czml
(the official verifier replay: positions, photos, batteries, validity, scores)."""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import ROOT, AAB, WORK, ASSETS, FFMPEG, AEOSSP_PACK, REVISIT_DATA  # noqa: E402,F401
import json, sys
import numpy as np
from datetime import datetime, timedelta
from matplotlib.collections import LineCollection
from matplotlib.animation import FFMpegWriter
import matplotlib.pyplot as plt
import viztemplate as V
plt.rcParams['animation.ffmpeg_path'] = FFMPEG
D = _os.path.join(WORK, 'viz', 'aeossp')
R = json.load(open(f'{D}/replay.json')); CZ = json.load(open(f'{D}/mission.czml')); OUT = sys.argv[1]; PREVIEW = '--preview' in sys.argv
H = R['mission']['horizon_s']; SAT = [s['id'] for s in R['satellites']]; NS = len(SAT)
T = R['tasks']; tlon = np.array([t['lon'] for t in T]); tlat = np.array([t['lat'] for t in T]); tw = np.array([t['w'] for t in T]); TOTW = tw.sum()
h0 = datetime.fromisoformat(R['mission']['start'].replace('Z', '+00:00')); clock = lambda s: (h0 + timedelta(seconds=float(s))).strftime('%H:%M UTC')
def ecef2ll(x, y, z):
    a, e2 = 6378137.0, 6.69437999014e-3; lon = np.degrees(np.arctan2(y, x)); p = np.hypot(x, y); lat = np.arctan2(z, p * (1 - e2))
    for _ in range(4):
        N = a / np.sqrt(1 - e2 * np.sin(lat) ** 2); lat = np.arctan2(z + e2 * N * np.sin(lat), p)
    return np.degrees(lat), lon
pos = {pk['id']: np.array(pk['position']['cartesian']).reshape(-1, 4) for pk in CZ[1:]}
LL = {}
for s in SAT:
    c = pos[s]; la, lo = ecef2ll(c[:, 1], c[:, 2], c[:, 3]); LL[s] = (c[:, 0], lo, la)
def sub(s, t):
    tt, lo, la = LL[s]; i = min(max(int(t // 30), 0), len(tt) - 2); f = (t - tt[i]) / (tt[i + 1] - tt[i])
    x0, y0, x1, y1 = lo[i], la[i], lo[i + 1], la[i + 1]
    if abs(x1 - x0) > 180: return (x0, y0) if f < 0.5 else (x1, y1)
    return (x0 + f * (x1 - x0), y0 + f * (y1 - y0))
TG = np.arange(0.0, H + 1, 60.0)
P = {}
for k, rk in (('base', 'baseline'), ('muse', 'muse')):
    pl = R['plans'][rk]; simEnd = {SAT[int(i)]: v for i, v in pl['sim_end'].items()}
    failT = {}
    for f in pl['failures']: failT[SAT[f[0]]] = min(failT.get(SAT[f[0]], 1e18), f[1])
    obs = np.array(pl['obs'], float); ok = obs[:, 3] <= np.array([simEnd[SAT[int(o)]] for o in obs[:, 0]]) + 1e-6
    first = {}
    for o, g in zip(obs, ok):
        if g and (int(o[1]) not in first or o[3] < first[int(o[1])]): first[int(o[1])] = o[3]
    comp = np.full(len(T), np.inf)
    for t_, e in first.items(): comp[t_] = e
    bat = [np.array(pl['battery'][str(i)]) for i in range(NS)]
    fleetmin = np.min([np.interp(TG, b[:, 0], b[:, 1], right=b[-1, 1]) for b in bat], axis=0)
    P[k] = dict(pl=pl, failT=failT, obs=obs, ok=ok, comp=comp, ends=np.sort(obs[ok, 3]), fleetmin=fleetmin)
f1 = min(P['base']['failT'].values()); s1 = min(P['base']['failT'], key=P['base']['failT'].get); nfail = len(P['base']['failT'])
F = V.frame('Earth-observation scheduling (AEOSSP)  ·  hard sealed mission (never seen by Muse)  ·  40 satellites  ·  12 hours',
            'Muse collects more photo value without letting any battery run empty', ('photo value collected', 'photos taken', 'plan'),
            'Lowest battery level in the whole fleet (Wh)')
fig = F['fig']; A = {}
for k, ax in F['map'].items():
    tg = ax.scatter(tlon, tlat, s=np.full(len(T), 2.5), c='#3a4760', lw=0, zorder=1)
    tr = LineCollection([], colors=[(0.75, 0.8, 0.88, 0.22)], lw=0.7, zorder=2); ax.add_collection(tr)
    sat = ax.scatter(np.zeros(NS), np.zeros(NS), s=28, c=V.COL[k], marker='D', edgecolors=V.BG, lw=0.6, zorder=5)
    dead = ax.scatter([], [], s=230, c=V.ALARM, marker='X', edgecolors=V.BG, lw=1.0, zorder=7)
    A[k] = dict(tg=tg, tr=tr, sat=sat, dead=dead)
fx, fy = sub(s1, f1)
an = F['map']['base'].annotate('Battery empty:\nthe whole plan is invalid', (fx, fy), xytext=(fx + (28 if fx < 100 else -95), fy + (22 if fy < 40 else -30)),
                               fontsize=V.MID, color=V.ALARM, fontweight='bold', zorder=9, arrowprops=dict(arrowstyle='-|>', color=V.ALARM, lw=1.8),
                               bbox=dict(boxstyle='round,pad=0.4', fc='#0b1220ee', ec=V.ALARM))
ch = F['chart']; ch.set_xlim(0, 12); ymax = max(P['base']['fleetmin'].max(), P['muse']['fleetmin'].max()) * 1.08; ch.set_ylim(-60, ymax)
ch.set_xticks(range(0, 13, 2)); ch.set_xticklabels([clock(h * 3600)[:5] for h in range(0, 13, 2)]); ch.set_xlabel('time (UTC)', fontsize=V.SMALL)
ch.axhline(0, color=V.ALARM, lw=1.4, ls='--'); ch.text(0.1, 18, '0 Wh: plan invalid', fontsize=V.SMALL, color=V.ALARM); ch.grid(axis='y', color='#1a2334', lw=0.6)
CL = {k: ch.plot([], [], color=V.COL[k], lw=2.6 if k == 'muse' else 2.0)[0] for k in P}
EL = {k: ch.text(0, 0, '', fontsize=V.SMALL, color=V.COL[k], fontweight='bold', va='center') for k in P}
XM = ch.scatter([f1 / 3600], [0], marker='X', s=140, color=V.ALARM, zorder=6, visible=False)
BEATS = [(0, f'{NS} satellites choose among {len(T):,} photo requests. Every photo uses battery energy.'),
         (5 * 3600, 'Both planners collect photo value at a similar rate.'),
         (31000, 'Slow motion: the baseline keeps taking photos while its batteries run low.'),
         (f1, f'{clock(f1)}: a baseline satellite runs out of battery. The whole plan now scores 0.'),
         (f1 + 3600, 'Muse keeps a safety margin on every battery and still collects more photo value.')]
def state(k, t):
    d = P[k]; done = int(np.searchsorted(d['ends'], t, side='right')); val = tw[d['comp'] <= t].sum() / TOTW
    fails = [s for s, f in d['failT'].items() if t >= f]; return done, val, fails
def draw(t, sp):
    F['clock'].set_text(clock(t)); F['speed'].set_text('' if sp is None else (f'slow motion (~{sp:.0f}x)' if sp < 400 else f'replay ~{sp:.0f}x'))
    ti = int(min(t, H) // 60)
    for k, a in A.items():
        d = P[k]; done, val, fails = state(k, t)
        cols = np.where((d['comp'] <= t)[:, None], np.array([[0.79, 0.82, 0.86, 0.9]]) if k == 'base' else np.array([[0.31, 0.63, 1.0, 0.95]]), np.array([[0.23, 0.28, 0.38, 0.8]]))
        a['tg'].set_facecolors(cols); a['tg'].set_sizes(np.where(d['comp'] <= t, 4.5, 2.5))
        xy = np.array([sub(s, t) for s in SAT]); a['sat'].set_offsets(xy)
        a['dead'].set_offsets(np.array([sub(s, d['failT'][s]) for s in fails]) if fails else np.zeros((0, 2)))
        segs = []
        for s in SAT:
            tt, lo, la = LL[s]; i1 = int(t // 30) + 1; i0 = max(i1 - 30, 0); p = np.column_stack([lo[i0:i1], la[i0:i1]])
            if len(p) > 1: segs += [q for q in np.split(p, np.where(np.abs(np.diff(p[:, 0])) > 180)[0] + 1) if len(q) > 1]
        a['tr'].set_segments(segs)
        k1, k2, k3 = F['kpi'][k]; bad = len(fails) > 0
        k1.set_text(f'{100 * val:.1f}%'); k1.set_color(V.FAINT if bad else V.COL[k]); k2.set_text(f'{done:,}')
        k3.set_text('INVALID' if bad else 'valid'); k3.set_color(V.ALARM if bad else V.COL[k])
        CL[k].set_data(TG[:ti + 1] / 3600, d['fleetmin'][:ti + 1]); EL[k].set_position((min(t, H) / 3600 + 0.08, d['fleetmin'][ti])); EL[k].set_text(V.TAG[k].lower() if ti > 30 else '')
    an.set_visible(t >= f1); XM.set_visible(t >= f1); F['caption'].set_text(V.beat(BEATS, t))
def intro():
    V.show_card(F, 'Earth-observation scheduling',
                f'{NS} imaging satellites, 12 hours, {len(T):,} photo requests with different values.\nEach photo costs time to turn the camera and battery energy. If one battery reaches 0, the whole plan is invalid.',
                notes=('BEFORE: a simple baseline planner (takes each photo in time order if it fits).',
                       'AFTER: the planner Muse discovered on its own, from only the problem, a simulator and a scorer.',
                       'This hard mission was sealed: Muse never saw it.'))
def outro():
    _, vb, fb = state('base', H); _, vm, fm = state('muse', H)
    V.show_card(F, 'Result on the sealed mission', 'Official AstroAgentBench verifier',
                rows=[('score (0-100)', f"{P['base']['pl']['N']:.0f}", f"{P['muse']['pl']['N']:.1f}", True), ('empty batteries', f'{len(fb)}', f'{len(fm)}', True),
                      ('photo value collected', f'{100 * vb:.1f}%', f'{100 * vm:.1f}%', True)],
                notes=('Across all 23 sealed missions, Muse beat the baseline on 23 of 23.',
                       'On normal missions the gain is modest (about +2 points); the best published solver still scores higher (75.95 vs 75.40 on the test set).'))
FPS = 20; sched = [(0, 31000, 20), (31000, 36600, 26), (36600, H, 9)]
times = []
for a_, b_, sec in sched: times += [(t, (b_ - a_) / sec) for t in np.linspace(a_, b_, int(sec * FPS), endpoint=False)]
if PREVIEW:
    for t in (6 * 3600, 32000, f1 + 600, H):
        draw(t, 215 if 31000 <= t < 36600 else 1550); fig.savefig(OUT.replace('.mp4', f'_t{int(t)}.png'), facecolor=V.BG)
    intro(); fig.savefig(OUT.replace('.mp4', '_intro.png'), facecolor=V.BG); outro(); fig.savefig(OUT.replace('.mp4', '_end.png'), facecolor=V.BG); sys.exit()
w = FFMpegWriter(fps=FPS, bitrate=7000, codec='libx264', extra_args=['-pix_fmt', 'yuv420p'])
with w.saving(fig, OUT, dpi=100):
    draw(0, None); intro()
    for _ in range(7 * FPS): w.grab_frame(facecolor=V.BG)
    V.hide_card(F)
    for t, sp in times: draw(t, sp); w.grab_frame(facecolor=V.BG)
    draw(H, None)
    for _ in range(1 * FPS): w.grab_frame(facecolor=V.BG)
    outro()
    for _ in range(9 * FPS): w.grab_frame(facecolor=V.BG)
print('wrote', OUT)
