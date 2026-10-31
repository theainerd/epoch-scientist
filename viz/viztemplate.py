"""Shared layout for the AstroAgentBench before/after videos (1920x1080).
Design rules: declutter + focus (one headline, one caption, one primary annotation), 3 text sizes, one colour per entity
(grey = baseline planner, blue = Muse, vermilion = failure only), no red/green pairs."""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import ROOT, AAB, WORK, ASSETS, FFMPEG, AEOSSP_PACK, REVISIT_DATA  # noqa: E402,F401
import json
import numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.patches import FancyBboxPatch

BG, PANEL, LAND, LAND_EDGE = '#0b0f17', '#0d1524', '#1d2738', '#2b3850'
TEXT, MUTED, FAINT = '#e8ecf2', '#93a0b4', '#5b6880'
BASE, MUSE, ALARM = '#b9c1cd', '#4ea1ff', '#ff5a4e'
BIG, MID, SMALL, KPI = 22, 15, 12, 30            # three text sizes + KPI numbers
NAME = {'base': 'Simple baseline planner', 'muse': 'Planner optimised by Muse'}
TAG = {'base': 'BEFORE', 'muse': 'AFTER'}
COL = {'base': BASE, 'muse': MUSE}
LANDFILE = _os.path.join(AAB, 'benchmarks/aeossp_standard/sources/ne_110m_land.geojson')


def land_polys():
    L = json.load(open(LANDFILE)); out = []
    for f in L['features']:
        g = f['geometry']; cs = g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]
        out += [np.array(p[0])[:, :2] for p in cs]
    return out


def frame(family, headline, kpi_labels, chart_title):
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': SMALL, 'text.color': TEXT, 'axes.labelcolor': MUTED,
                         'xtick.color': MUTED, 'ytick.color': MUTED, 'axes.edgecolor': FAINT, 'xtick.labelsize': SMALL, 'ytick.labelsize': SMALL})
    fig = plt.figure(figsize=(19.2, 10.8), dpi=100, facecolor=BG)
    F = dict(fig=fig)
    fig.text(0.02, 0.962, 'ASTROAGENTBENCH', fontsize=SMALL, color=MUSE, fontweight='bold')
    fig.text(0.128, 0.962, family, fontsize=SMALL, color=MUTED)
    F['headline'] = fig.text(0.02, 0.918, headline, fontsize=BIG, fontweight='bold', color=TEXT)
    F['clock'] = fig.text(0.98, 0.928, '', fontsize=BIG, fontweight='bold', ha='right', family='DejaVu Sans Mono')
    F['speed'] = fig.text(0.98, 0.962, '', fontsize=SMALL, ha='right', color=MUTED)
    polys = land_polys(); F['map'] = {}; F['kpi'] = {}
    for i, k in enumerate(('base', 'muse')):
        x0 = 0.02 + i * 0.49
        ax = fig.add_axes([x0, 0.405, 0.47, 0.44]); ax.set_xlim(-180, 180); ax.set_ylim(-62, 84); ax.set_xticks([]); ax.set_yticks([])
        ax.set_facecolor(PANEL); ax.add_collection(PolyCollection(polys, facecolor=LAND, edgecolor=LAND_EDGE, lw=0.4, zorder=0))
        for sp in ax.spines.values(): sp.set_color(COL[k] if k == 'muse' else FAINT); sp.set_linewidth(1.6 if k == 'muse' else 1.0)
        F['map'][k] = ax
        fig.text(x0, 0.856, TAG[k], fontsize=MID, fontweight='bold', color=COL[k])
        fig.text(x0 + (0.058 if k == 'base' else 0.050), 0.856, NAME[k], fontsize=MID, color=TEXT)
        F['kpi'][k] = []
        for j, lab in enumerate(kpi_labels):
            xx = x0 + 0.01 + j * 0.155
            v = fig.text(xx, 0.338, '', fontsize=KPI, fontweight='bold', color=COL[k])
            fig.text(xx, 0.315, lab, fontsize=SMALL, color=MUTED)
            F['kpi'][k].append(v)
    F['caption'] = fig.text(0.5, 0.268, '', fontsize=MID + 2, ha='center', va='center', color=TEXT,
                            bbox=dict(boxstyle='round,pad=0.55', fc='#121b2c', ec='#26324a', lw=1))
    ch = fig.add_axes([0.06, 0.07, 0.86, 0.125]); ch.set_facecolor(BG)
    for s in ('top', 'right'): ch.spines[s].set_visible(False)
    ch.set_title(chart_title, loc='left', fontsize=MID, color=TEXT, pad=8); F['chart'] = ch
    fig.text(0.98, 0.012, 'Orbits, photo times and scores: official AstroAgentBench verifier. Map and labels are display only.', fontsize=SMALL - 1, color=FAINT, ha='right')
    # full-screen card (intro / end)
    cardax = fig.add_axes([0, 0, 1, 1], zorder=50); cardax.axis('off'); cardax.set_xlim(0, 1); cardax.set_ylim(0, 1)
    cardax.add_patch(plt.Rectangle((0, 0), 1, 1, color=BG, alpha=1.0)); F['card'] = cardax; F['card_items'] = []
    cardax.set_visible(False)
    add_brand(fig)
    return F


BRAND_DIR = ASSETS


def add_brand(fig):
    """Footer brand row (bottom-left, above every layer): the Meta mark.
    Uses meta_logo.png if it exists in BRAND_DIR, otherwise a text mark."""
    import os, matplotlib.image as mi
    H = 0.040; w = -0.098
    mp = os.path.join(BRAND_DIR, 'meta_logo.png')
    if os.path.exists(mp):
        ml = mi.imread(mp); mw = H * 1080 / 1920 * ml.shape[1] / ml.shape[0]
        fig.text(0.124 + w, 0.026, 'Built with', fontsize=SMALL, color=MUTED, va='center', zorder=61)
        b = fig.add_axes([0.172 + w, 0.006, mw, H], zorder=60); b.imshow(ml); b.axis('off')
    else:
        fig.text(0.124 + w, 0.026, 'Built with', fontsize=SMALL, color=MUTED, va='center', zorder=61)
        fig.text(0.170 + w, 0.026, 'Meta Muse', fontsize=SMALL + 1, fontweight='bold', color=TEXT, va='center', zorder=61)


def show_card(F, title, sub, rows=None, notes=()):
    """rows: list of (label, before, after) shown as large before -> after numbers."""
    ax = F['card']
    for it in F['card_items']: it.remove()
    F['card_items'] = []; add = F['card_items'].append
    add(ax.text(0.5, 0.86, 'ASTROAGENTBENCH', ha='center', fontsize=MID, color=MUSE, fontweight='bold'))
    add(ax.text(0.5, 0.80, title, ha='center', fontsize=BIG + 8, fontweight='bold', color=TEXT))
    add(ax.text(0.5, 0.74, sub, ha='center', va='top', fontsize=MID + 3, color=MUTED, linespacing=1.6))
    if rows:
        n = len(rows)
        for j, (lab, a, b, good) in enumerate(rows):
            cx = 0.5 + (j - (n - 1) / 2) * 0.30
            add(ax.add_patch(FancyBboxPatch((cx - 0.13, 0.33), 0.26, 0.24, boxstyle='round,pad=0.01', fc='#111a2a', ec='#26324a')))
            add(ax.text(cx, 0.525, lab, ha='center', fontsize=MID, color=MUTED))
            add(ax.text(cx - 0.065, 0.43, a, ha='center', fontsize=KPI + 6, fontweight='bold', color=BASE))
            add(ax.text(cx, 0.43, '\u2192', ha='center', fontsize=KPI, color=FAINT))
            add(ax.text(cx + 0.065, 0.43, b, ha='center', fontsize=KPI + 6, fontweight='bold', color=MUSE))
            add(ax.text(cx - 0.065, 0.365, 'before', ha='center', fontsize=SMALL, color=FAINT)); add(ax.text(cx + 0.065, 0.365, 'after', ha='center', fontsize=SMALL, color=FAINT))
    y0 = 0.24 if rows else 0.56
    for i, nline in enumerate(notes):
        add(ax.text(0.5, y0 - i * 0.06, nline, ha='center', fontsize=MID + 1, color=MUTED if i == len(notes) - 1 and i else TEXT))
    ax.set_visible(True)


def hide_card(F):
    F['card'].set_visible(False)


def beat(beats, t):
    """beats: list of (t_from, text) sorted; returns the active text."""
    cur = ''
    for t0, txt in beats:
        if t >= t0: cur = txt
    return cur
