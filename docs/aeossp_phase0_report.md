# MissionPilot — Phase 0 report (AstroAgentBench `aeossp_standard`)

Date: 29 Oct 2026, 23:20 IST. Repo: Mtrya/AstroAgentBench, main-branch tarball (git clone is blocked in the sandbox). Env: Python 3.13, brahe 1.8.0, scipy/HiGHS. Machine: 6-core Mac, 8 GB.
Score: paper reporting score N = 100(0.45 WCR + 0.20 CR + 0.20[1-TAT/H] + 0.15[1-PC/E_bud]); `nscore.py` reproduces the paper's worked example (70.87).

## 1. Phase 0 measurements

| Measurement | Result |
|---|---|
| Baseline score (test, 5 cases) | greedy_lns N 71.63, WCR 0.681 (paper 71.65 / 0.682). MWIS N 75.95, WCR 0.758 (paper 75.95 / 0.758). Reproduced. |
| Baseline score (train, 10 cases) | greedy_lns N 72.56, WCR 0.689. MWIS N 76.94, WCR 0.766. All 30 runs valid. |
| Strongest reference | MWIS conflict graph, not greedy_lns. It is the bar to beat. |
| Solve time | greedy_lns 122 s, MWIS 172 s per case (1 core, uncontended). Candidate generation is 113 s of this (93% for greedy). |
| Verification time | 3.5 s per case uncontended; 4–11 s with 4 parallel jobs. |
| Dataset splits | train 10; test 5; test_easy 5; test_hard 5; test_horizon_2022 5. |
| Runtime compatibility | Harbor's own `score.py` on the packaged task gives metrics identical to the direct verifier call. No Docker here; Python-only scoring is equivalent. Sandbox sets PYTHONSAFEPATH=1, so PYTHONPATH must be set. |
| Extra effort for MWIS | README fair-run profile (300 s, 16/8/24) on train 1–3: WCR 0.830/0.779/0.747 vs default 0.830/0.781/0.747. No gain. |

## 2. Ceiling (train cases only; the test split was not used)

| Train case | greedy WCR | MWIS WCR | Exact MILP WCR (all conflicts, battery relaxed) | Loose bound (no slew) |
|---|---|---|---|---|
| case_0001 | 0.755 | 0.830 | not run | 0.904 |
| case_0002 | 0.699 | 0.781 | 0.7939 (optimal, 8 s) | 0.875 |
| case_0003 | 0.662 | 0.747 | 0.7557 (optimal, 8 s) | 0.835 |

The MILP schedules pass the official verifier, battery included:

| Train case | MWIS N | MILP N | Gain |
|---|---|---|---|
| case_0002 | 77.83 | 78.47 | +0.64 |
| case_0003 | 74.93 | 75.39 | +0.46 |

Interpretation: the candidate grid is the full 5 s action grid. MILP max-weight independent set (HiGHS, task cliques + overlap + slew-transition edges) reaches the proven WCR optimum on that grid in about 8 s, and battery does not bind. MWIS is already within about 0.01 WCR (about 0.5 N) of the optimum. The remaining terms give little: TAT is about 19.5 of 20 points, and each extra observation costs about 0.003 N in energy against about 0.03 N in weight.

## 3. Feasibility of evolving the solver

- Compute: feasible. Cache the candidates per case once; then one evaluation is about 60 s per case, and 10 train cases on 4 cores take about 3 min.
- Headroom: NOT sufficient. The best possible gain over MWIS is about +0.5 N on the official score, and a textbook MILP reaches it in seconds. An AI scientist could only rediscover a MILP. The 3.04-point gap in the paper is an agent shortfall, not open headroom.

## 4. Decision

NO-GO for the research claim "AI Scientist discovers a planner that beats conventional planners" on `aeossp_standard`. The benchmark is effectively solved at about 8 s per case.
Do not commit to MissionPilot on AEOSSP. Before you choose a pivot, run the same one-hour ceiling test on another AstroAgentBench family where agents beat the solvers (SatNet +7.86, Revisit +5.52, Relay +3.12 in the paper).

Files: `phase0_repro.csv` (30 runs), `nscore.py`, `bound.py` (loose bound), `bound2.py` (exact MILP), `run_one.sh`.
