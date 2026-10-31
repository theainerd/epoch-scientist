# Method: a blind, evolutionary AI scientist

## 1. Blind task packs (`tasks/<problem>/`)
Muse receives only:
* `task.md`: the problem in plain language, the rules, the score, the program contract (`solve(world, time_limit_s)`), and
  how to work. No method hints, no papers, no published scores.
* `sim.py`: physics helpers (for Revisit: exact propagation plus a fast J2-secular estimate that agrees with the exact
  propagator to 5-30 km over 48 h at ~1000x the speed; for AEOSSP: pre-computed observation opportunities and an exact local
  check of the verifier's rules).
* `evaluate.py`: runs the program on the development missions, one fresh process per mission, one CPU thread, fixed time
  limit (60 s AEOSSP, 200 s Revisit), then scores the plan with the frozen verifier. A crash, a time-out or an invalid plan
  scores 0 for that mission; a modified helper or verifier file (SHA-256 check) gives -100.
* `program_0`: a simple, honest starting program (AEOSSP: take photos in time order if they fit; Revisit: an evenly spread
  constellation at the satellite cap, 700 km, 55 deg, with greedy photos).
Only development missions are shipped (AEOSSP train 1-7, Revisit train 1-4). All other missions stay sealed.

## 2. The search: Meta Muse Wonder (model) + OpenCode (agent harness) + AI-Scientist-v3 (research loop)
AI-Scientist-v3 manages workers, cycles, memory, rubrics and selection. Every idea and every implementation step is an
OpenCode coding-agent session (bash, file edits, running the evaluator) driven by Muse Wonder (`meta/muse-wonder-1.0`).
Two workers run 10 cycles each in parallel. One cycle:
1. **Read memory:** lessons from every earlier attempt, including the other worker's conclusions.
2. **Propose one idea:** a hypothesis and success checks (rubrics).
3. **Change the program:** Muse edits a copy of its worker's current best program (the parent).
4. **Score it:** the frozen verifier on the development missions.
5. **Select:** if every mission is valid and the score beats the worker's best, the program becomes the new parent;
   otherwise it is discarded and only its lesson is kept. (A worker's first fully valid program becomes its parent even if it
   is below the start.)

We verified the lineage from program SHA-256 hashes (`analysis/extract_runs.py`). The shared memory carried real ideas
across workers: in AEOSSP, worker 2's best program (cycle 8, contention-priced construction) follows a shared lesson that
recommends Lagrangian pricing, which worker 1 introduced in cycle 7; in Revisit, worker 2 cycle 5 builds on worker 1's
cycle-4 result.

Run settings: model `meta/muse-wonder-1.0` ($4 / $20 per 1M input/output tokens), reasoning effort high when the provider accepts it, Kaggle CPU notebook,
web tools disabled, budget guard at $40, W&B monitoring. Before any paid run, a free preflight checks that the harness scores
`program_0` exactly as expected (AEOSSP 74.926186, Revisit 69.820818).

## 3. Judging
After the run, the best development program is scored on the sealed missions with the same evaluator, and compared with
hidden yardsticks: the benchmark's reference solvers, an exact MILP on the conflict graph (AEOSSP), a plain Walker sweep
(Revisit), and the paper's published agent results.
