# Results and limits

All numbers come from the frozen official verifiers. Tables: `results/summary.csv`, `results/*/sealed_per_mission.csv`,
`results/*/ideas_table.csv`, yardsticks in `results/aeossp/yardsticks_train.csv`, `results/aeossp/hard_missions_yardsticks.csv` and
`results/revisit/yardstick_j2_solver.csv`; hard-mission solver plans in `results/aeossp/hard_yardsticks_raw/` (re-check with
`analysis/reverify_hard_yardsticks.py`); code originality in `results/code_originality.csv`; run logs in `results/wandb/`.

| | AEOSSP | Revisit |
|---|---|---|
| Model / attempts / workers | Muse Wonder 1.0 / 20 / 2 | Muse Wonder 1.0 / 20 / 2 |
| Cost, wall time | $27.66, 113 min | $29.10, 105 min |
| Failed attempts (crash or unscored) | 0 | 0 |
| Dev score: start -> Muse | 74.93 -> 76.63 | 69.82 -> 77.82 |
| Sealed | 23/23 missions better than start | 67.35 -> 77.07 mean (11 missions) |
| Versus the benchmark solver | below MWIS (75.40 vs 75.95 on test; 78.54 vs 79.25 on the 5 hard missions) | above j2 set cover on 4 of 5 sealed missions and on 18 of 20 fresh missions (76.40 vs 72.45; 14.9 vs 17.0 satellites) |
| Hard missions (5), start invalid | Muse valid on 5/5; MWIS 79.25 and greedy_lns 75.15 also valid on 5/5 | |
| Code shared with reference solvers | 0.35% (unrelated-problem floor 0.0%) | 0.33% (floor 0.05%) |
| Versus the paper's best agent | above Codex + GPT-5.4 (75.40 vs 72.91 on test)* | below Claude Code + Opus 4.6 (16.0 vs 11.4 satellites on test)* |

\* not like-for-like: the paper's agents worked per mission with hours of compute and (AEOSSP) computed geometry themselves;
Muse writes one general program under a fixed per-mission time limit.

## Limits
1. One run per problem, one seed.
2. Muse mostly recombined established optimisation methods (greedy construction, destroy-and-repair, ejection chains,
   Lagrangian prices, orbit-family search). This is automatic engineering, not new science.
3. Selection on development missions did not always pick the program that generalises best (Revisit runner-up).
4. The starting programs were written by us; the gains are measured from them, and the hidden yardsticks show where they sit.

## Fresh-mission test (Revisit, 2 Nov 2026)

20 new missions from the benchmark generator (seed 314159), rules fixed first ([PREREG.md](../results/revisit/fresh_missions/PREREG.md)). Muse beat j2 on 18 of 20; mean score start 63.10, Muse 76.40, j2 72.45; mean satellites 18.8 / 14.9 / 17.0; every target met 5 / 16 / 17; valid 20 / 20 / 20. Cyclone watch (30 cities, 6 h, 20 satellites): start 67.00 (3 missed), Muse 69.59 (3 missed), j2 70.00 (0 missed). Details: [results/revisit/fresh_missions/](../results/revisit/fresh_missions/README.md).
