# Goal
Design a small Earth-observation constellation and its photo plan. A mission has 24-32 ground targets and lasts 48 hours.
Every target must be photographed again and again: the longest time without a photo (the "revisit gap") must stay at or
below the target's revisit requirement (6 or 8 hours). You choose how many satellites to launch (at most `cap`, 16-20),
the orbit of each satellite, and which photos each satellite takes. Fewer satellites are better, but only once every
target meets its requirement. Write `solve(world, time_limit_s)` that returns the satellites and the photo plan.
The score is measured on 4 development missions; the final evaluation re-runs the program on sealed missions of the same
kind that are not on this machine, so the method must work on new missions, not on these 4 only.

# The world (what the program receives)
`world` is a dict built by the evaluator; `sim.py` lists every field. In short: mission start/end, `horizon_s` (172,800 s),
`cap`, the satellite model (sensor limits, slew limits, settling time, battery and power use, allowed altitude band),
the targets (latitude, longitude, revisit requirement, minimum elevation, maximum slant range, minimum photo duration),
`times` (the 10 s time grid) and `rot` (inertial -> Earth-fixed rotation on that grid). All satellites use the same model.

# Rules of a valid plan (checked by the frozen official verifier; one violation makes the mission score 0)
1. At most `cap` satellites. Each satellite is an inertial (ECI) position and velocity at mission start (m, m/s). Its orbit is
   propagated with Earth gravity including J2 only. Perigee and apogee altitude must stay inside the allowed altitude band.
2. A photo (satellite i, target j, start s, end e, seconds from mission start) is valid only if e - s >= the target's minimum
   duration and, at s, s+10, s+20, ... (< e): elevation >= the target's minimum elevation, slant range <= the target and
   sensor limits, and off-nadir angle <= the sensor limit.
3. On one satellite, photos must not overlap, and consecutive photos need time to turn the camera:
   e_prev + sim.slew_time(angle, world) + settling time <= s_next (angle between the two lines of sight at the photo midpoints).
4. The battery of every satellite must never fall below 0 (imaging and turning use energy; sunlight charges it).
5. The revisit gap of a target is the longest interval between consecutive photo midpoints, counting the mission start and
   end as boundaries. Photos of the same target by different satellites all count.
`sim.official_check(world, satellites, actions)` runs the frozen official verifier locally (about 10-20 s) and returns
(valid, metrics, errors, score). `sim.exact_propagate` gives the exact verifier trajectories (about 1 s per satellite).
`sim.state_from_elements` + `sim.fast_positions` give an approximate trajectory in about 1 ms per satellite (error about
5-30 km over 48 h) for fast screening; final plans must be checked with exact trajectories.

# Score (higher is better)
Per mission, for a valid plan with n satellites and per-target revisit gaps g_j (hours), requirement r_j, horizon H = 48 h:
- If every target meets its requirement (g_j <= r_j for all j):  score = 70 + 30 * (cap - n) / (cap - 1).
- Otherwise:  score = 70 * mean_j phi_j, with phi_j = 1 if g_j <= r_j, else ((H - g_j) / (H - r_j))^2.
- An invalid plan, an exception, or a time-out gives 0 for that mission. If the evaluator itself cannot run the program,
  combined_score = -100.
`sim.mission_score` computes this. combined_score = mean over the 4 development missions. program_0 (an evenly spread
constellation at the cap, 700 km, 55 deg, plus a time-ordered greedy photo plan) is the baseline.

# Program contract
- `program.py` defines `solve(world, time_limit_s) -> {'satellites': [6-vectors], 'actions': [(sat_index, target_index, start_s, end_s), ...]}`.
  Indices start at 0; times are seconds from mission start.
- Each mission runs in a fresh process with ONE CPU thread. `solve` must return within `time_limit_s` = 200 s per mission
  (measured wall-clock; over 200 s gives 0). Use `time.time()` to stop in time.
- Use only the `world` argument, `sim.py`, the Python standard library, numpy, scipy and brahe. Do not read files, environment
  variables or the network, and do not install packages.
- Be deterministic: fix every random seed.

# Rules
1. Do not change `evaluate.py`, `capture.py`, `sim.py`, `revisit_verifier.py` or `task.md` (copy a helper into program.py to
   change it). Score changes from evaluator edits are void (the evaluator checks file hashes).
2. No web search or web fetch. Work from the problem statement, the data and your own experiments.
3. The same program, unchanged, must handle every mission; do not hard-code per-mission choices.

# How to work
- EVALUATION TIMEOUT (most important): when you run the official evaluation command, ALWAYS pass the bash tool parameter
  `timeout: 3600000`. A full evaluation takes 3-8 minutes on this machine. The tool's default timeout can stop it, and you
  have only one evaluation per attempt.
- Before the official evaluation, test on 1-2 missions: `w = sim.build_world(evaluate.find_pack() + '/cases/train/case_0001')`,
  then `sim.official_check(w, ...)`. Keep the run time of `solve` well under 200 s on one thread.
- Every idea's target_rubrics must include an implementation rubric: "program.py defines solve(world, time_limit_s), uses only
  world/sim/numpy/scipy/brahe/stdlib, returns within 200 s per mission, and leaves evaluate.py, capture.py, sim.py and
  revisit_verifier.py unchanged".
- Read `per_case` in metrics.json (n_satellites, n_targets_missing, worst_gap_h per mission), not only combined_score.
