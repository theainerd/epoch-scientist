# Pre-registration: fresh-mission generalisation test (written 2 Nov 2026, about 17:45 IST, before any j2 result)

**Question.** Does Meta Muse Wonder's frozen best Revisit program (results/revisit/programs/best_w2_cycle10.py, unchanged)
still beat the benchmark's expert solver (j2_rgt_set_cover) on missions nobody has seen?

**Missions.** 20 new missions made with the benchmark's own generator (generator/run.py) and its test-split settings,
new seed 314159 (target_selection_seed_offset 977). Max target-set overlap with any official mission: 0.286 (Jaccard).
Missions 1-20 of 30 generated; the 20 were fixed before any run (time budget for j2: about 25-40 min per mission).

**Programs.** Muse best (frozen), start program (program_0), j2_rgt_set_cover (benchmark solver, default settings).
All plans scored by the frozen official verifier and the task's per-mission rule (sim.mission_score), as in the README.

**Reported, all of them, whatever the result:**
1. Primary: number of missions (of 20) where Muse's score > j2's score.
2. Mean score: start, Muse, j2.
3. Mean satellites: start, Muse, j2.
4. Missions where every target meets its revisit requirement: start, Muse, j2.
5. Valid plans: start, Muse, j2.

**Pre-stated expectation (from the 5 official sealed missions, where Muse won 4 of 5):** Muse beats j2 on at least 12 of 20.
If Muse wins fewer than 10 of 20, the README says so and the headline claim is weakened accordingly.

**Real-world use case ("cyclone watch").** Fixed before any run: 30 coastal cities often hit by tropical cyclones,
6 h revisit, 48 h, cap 20 satellites, benchmark target defaults and satellite model. Reported as is, whatever the result.
