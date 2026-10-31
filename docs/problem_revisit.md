# Problem 2: Revisit Constellation design

**Task.** 24-32 ground targets, 48 hours. Every target must be photographed again at least every 6 or 8 hours. Choose how
many satellites to launch (cap 16-20), each satellite's orbit, and every photo. Fewer satellites are better, but only once
every target meets its requirement.

**Starting program:** an evenly spread constellation at the cap, 700 km, 55 deg, greedy photos (dev 69.82).

**Development missions:** train 1-4. **Sealed:** train 5-10 and test 1-5 (11 missions).

**Hidden yardsticks:** j2_rgt_set_cover solver (dev 72.47, 70 satellites); a plain Walker sweep; the paper's agents.

**Best program:** worker 2, cycle 10, "Geometry-Diverse Constructive Growth" (`results/revisit/programs/best_w2_cycle10.py`):
dev 77.82 with 13/17/17/10 satellites (57 in total; start 76, solver 70).

| Sealed result | Start | Muse best |
|---|---|---|
| Mean score, 11 sealed missions | 67.35 | **77.07** (11/11 valid; misses some targets on 2) |
| Mean score, train 5-9 (solver: 72.17) | - | **78.54** (better than the solver on 4 of 5) |

| Test, paper metric (G = mean requirement-floored gap; 6.80 h = every target met) | G (h) | Mean satellites |
|---|---|---|
| Claude Code + Opus 4.6 | 6.80 | 11.4 |
| Kimi CLI + Kimi K2.6 | 6.84 | 14.4 |
| Muse runner-up (worker 1, cycle 8) | 6.80 | 15.4 |
| Codex CLI + GPT-5.4 | 7.67 | 16.0 |
| **Muse best** | 6.807 | 16.0 |
| OpenCode + DeepSeek V4 Pro | 6.84 | 17.0 |
| Ref1 (benchmark solver) | 6.80 | 17.2 |
| Start program | 8.494 | 19.8 |

Example (sealed train 7, in the video): start 20 satellites, 30 of 31 targets on time (one target at 59.9 N is beyond its
55 deg orbits), score 67.74; Muse 10 satellites in 2 near-polar planes (97.5 deg, about 790 km), 31 of 31, worst gap 7.9 h,
score 85.79; the benchmark solver needs 15 satellites there.

Caveats: the runner-up generalises better on test but has a slew-timing bug that makes one sealed plan invalid; the best
paper agent uses fewer satellites but planned each mission directly with hours of compute, while Muse's program must solve
any mission in 200 s on one thread.
