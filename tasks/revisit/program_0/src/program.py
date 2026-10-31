"""Starting program: evenly spread constellation (planes x satellites per plane) at the satellite cap, 700 km, 55 deg,
then a time-ordered greedy photo plan (one 30 s photo near the middle of each visibility window, if the slew fits)."""
import math
import numpy as np
import sim


def constellation(n, alt_m=700e3, inc_deg=55.0, F=1):
    planes = max(1, int(round(math.sqrt(n))))
    while n % planes: planes -= 1
    per = n // planes
    return [sim.state_from_elements(alt_m, inc_deg, 360.0 * p / planes, 360.0 * s / per + 360.0 * F * p / n) for p in range(planes) for s in range(per)]


def schedule(world, states):
    eci, ecef, props = sim.exact_propagate(world, states)
    att = world['model']['attitude_model']; ts = world['times']; H = world['horizon_s']; actions = []
    for i in range(len(states)):
        vis = sim.visible(world, ecef[i]); cands = []
        for j, t in enumerate(world['targets']):
            dur = t['min_duration_sec']; need = int(math.ceil(dur / sim.STEP_S))
            d = np.diff(np.r_[0, vis[j].astype(int), 0]); st, en = np.where(d == 1)[0], np.where(d == -1)[0]
            for a, b in zip(st, en):
                if b - a >= need:
                    s0 = ts[a + (b - a - need) // 2]
                    if s0 + dur <= H: cands.append((s0, j, dur))
        cands.sort(); last = None
        for s0, j, dur in cands:
            los = sim.line_of_sight_eci(world, props[i], j, s0 + dur / 2)
            if last is not None and s0 - last[1] < sim.slew_time(sim.angle_deg(los, last[0]), world) + att['settling_time_sec'] + 1e-6:
                continue
            actions.append((i, j, float(s0), float(s0 + dur))); last = (los, s0 + dur)
    return actions


def solve(world, time_limit_s):
    states = constellation(world['cap'])
    return {'satellites': states, 'actions': schedule(world, states)}
