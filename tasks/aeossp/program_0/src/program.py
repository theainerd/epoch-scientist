"""Starting program: walk through all opportunities in time order and take each one that fits.

An opportunity is taken if its task is not done yet and the satellite has enough time to turn to it
after its previous observation (or from nadir, for its first observation). Battery is not considered.
"""
import numpy as np
import sim


def solve(world, time_limit_s):
    order = np.lexsort((world['sat'], world['start_s']))       # by start time, then satellite
    last = {}                                                   # satellite -> last taken opportunity
    done = set()
    chosen = []
    for k in order:
        k = int(k); t = int(world['task'][k]); s = int(world['sat'][k])
        if t in done:
            continue
        p = last.get(s)
        if p is None:
            ok = world['start_s'][k] >= world['nadir_slew_s'][k]
        else:
            ok = world['start_s'][k] - world['end_s'][p] >= sim.required_gap_s(world, p, k)
        if ok:
            chosen.append(k); last[s] = k; done.add(t)
    return chosen
