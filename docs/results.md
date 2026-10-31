# Results and limits

All numbers come from the frozen official verifiers. Tables: `results/summary.csv`, `results/*/sealed_per_mission.csv`,
`results/*/ideas_table.csv`, yardsticks in `results/aeossp/yardsticks_train.csv` and `results/revisit/yardstick_j2_solver.csv`.

| | AEOSSP | Revisit |
|---|---|---|
| Model / attempts / workers | Muse Wonder 1.0 / 20 / 2 | Muse Wonder 1.0 / 20 / 2 |
| Cost, wall time | $27.66, 113 min | $29.10, 105 min |
| Failed attempts (crash or unscored) | 0 | 0 |
| Dev score: start -> Muse | 74.93 -> 76.63 | 69.82 -> 77.82 |
| Sealed | 23/23 missions better than start | 67.35 -> 77.07 mean (11 missions) |
| Versus the benchmark solver | below MWIS (75.40 vs 75.95 on test) | above j2 set cover on 4 of 5 sealed missions |
| Versus the paper's best agent | above Codex + GPT-5.4 (75.40 vs 72.91 on test)* | below Claude Code + Opus 4.6 (16.0 vs 11.4 satellites on test)* |

\* not like-for-like: the paper's agents worked per mission with hours of compute and (AEOSSP) computed geometry themselves;
Muse writes one general program under a fixed per-mission time limit.

## Limits
1. One run per problem, one seed.
2. Muse mostly recombined established optimisation methods (greedy construction, destroy-and-repair, ejection chains,
   Lagrangian prices, orbit-family search). This is automatic engineering, not new science.
3. Selection on development missions did not always pick the program that generalises best (Revisit runner-up).
4. The starting programs were written by us; the gains are measured from them, and the hidden yardsticks show where they sit.
