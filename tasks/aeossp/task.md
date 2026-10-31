# Goal
Plan Earth-observation satellites. A constellation of 20-28 agile imaging satellites must photograph ground targets
during one 12-hour mission. Each target ("task") has a value (weight), a time window, a required photo duration and a
required sensor type. There are about 1,700-1,950 tasks per mission, far more than the satellites can photograph.
Write `solve(world, time_limit_s)` that chooses which observations to make so that the mission score is as high as possible.
The score is measured on 7 development missions; the final evaluation re-runs the program on sealed missions of the same
kind that are not on this machine, so the method must work on new missions, not on these 7 only.

# The world (what the program receives)
`world` is a dict built by the evaluator (see `sim.py` for the full field list). The physics is pre-computed:
- n "opportunities" (about 27,000-37,000 per mission). Opportunity k means "satellite `sat[k]` photographs task `task[k]`
  from `start_s[k]` to `end_s[k]`" (seconds from mission start). Every opportunity already satisfies the task's time window,
  exact duration, sensor type, line of sight and off-nadir limit. `weight[k]` is the value of its task.
- `look_start[k]`, `look_end[k]`: unit pointing direction of the camera at the start and end of opportunity k.
- `nadir_slew_s[k]`: time the satellite needs to turn from straight-down pointing to opportunity k.
- `satellites`: slew speed/acceleration limits, settling time, battery capacity, initial charge, power use
  (idle, imaging, slewing) and solar charging power. `sunlit[s, i]`: satellite s is in sunlight at time i*sunlit_step_s.
- `tasks`: id, weight, release_s, due_s, duration_s, sensor, lat_deg, lon_deg.

# Rules of a valid plan (checked by the frozen official verifier; one violation makes the whole mission score 0)
1. On one satellite, observations must not overlap in time.
2. Between two consecutive observations i -> j on one satellite: `start_s[j] - end_s[i] >= sim.required_gap_s(world, i, j)`
   (time to turn the camera plus settling). Before a satellite's first observation: `start_s[j] >= nadir_slew_s[j]`.
3. The battery of every satellite must never fall below 0 Wh. Idle power is always drawn; imaging power during an
   observation; slewing power during the required gap before each observation; solar charging while sunlit; the battery
   is capped at its capacity.
4. A task counts once (a second observation of the same task adds nothing but costs energy).
`sim.check(world, selection)` runs all these checks locally in about 0.1 s and returns the same score as the official
verifier. Use it freely.

# Score (higher is better)
Per mission: N = 100 * (0.45*WCR + 0.20*CR + 0.20*(1 - TAT/H) + 0.15*(1 - PC/E))
- WCR: completed task weight / total task weight;  CR: completed tasks / all tasks
- TAT: mean time from task release to the end of its first observation (s); H = 43,200 s
- PC: total energy used by all satellites (Wh); E = sum of battery capacities
- An invalid plan, an exception, or a time-out gives N = 0 for that mission. If the evaluator itself cannot run the program, combined_score = -100.
combined_score = mean N over the 7 development missions. program_0 (take opportunities in time order if they fit) is the baseline.

# Program contract
- `program.py` defines `solve(world, time_limit_s) -> list[int]` (indices of the chosen opportunities).
- Each mission runs in a fresh process with ONE CPU thread. `solve` must return within `time_limit_s` = 60 s per mission
  (measured wall-clock; over 60 s gives N = 0). Use `time.time()` to stop in time.
- Use only the `world` argument, `sim.py`, the Python standard library, numpy and scipy. Do not read files, environment
  variables or the network, and do not install packages.
- Be deterministic: fix every random seed.

# Rules
1. Do not change `evaluate.py`, `capture.py`, `sim.py`, `aab_verifier.py` or `task.md` (copy a helper into program.py to change it). Score changes from
   evaluator edits are void (the evaluator checks file hashes).
2. No web search or web fetch. Work from the problem statement, the data and your own experiments.
3. The same program, unchanged, must handle every mission; do not hard-code per-mission choices.

# How to work
- EVALUATION TIMEOUT (most important): when you run the official evaluation command, ALWAYS pass the bash tool parameter
  `timeout: 3600000`. A full evaluation takes 4-7 minutes on this machine. The tool's default timeout can stop it, and you have only one
  evaluation per attempt.
- Before the official evaluation, test your program on 1-2 missions with `sim.check` (load a world with
  `evaluate.load_world(evaluate.find_pack(), 'train', 'case_0001')`) and keep the run time of `solve` well under 60 s.
- Every idea's target_rubrics must include an implementation rubric: "program.py defines solve(world, time_limit_s), uses only
  world/sim/numpy/scipy/stdlib, returns within 60 s per mission, and leaves evaluate.py, capture.py, sim.py and aab_verifier.py unchanged".
- Read `per_case` in metrics.json (WCR, CR, TAT, PC per mission), not only combined_score.
