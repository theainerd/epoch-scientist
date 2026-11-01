# Problem 1: agile Earth-observation scheduling (AEOSSP)

**Task.** 20-40 agile imaging satellites, a 12-hour mission, about 1,700-4,000 photo requests ("tasks"), each with a value,
a time window, a duration and a sensor type. Choose the photos so that the mission score N is as high as possible, without
breaking any rule. The hard part: every photo costs camera-turn time and battery energy, and one empty battery voids the plan.

**Starting program:** take opportunities in time order whenever they fit (dev score 74.926).

**Development missions:** train 1-7. **Sealed:** train 8-10, test, test_easy, test_hard, test_horizon_2022 (23 missions).

**Hidden yardsticks (dev):** greedy_lns 72.90, MWIS 77.40, exact MILP on the conflict graph 77.79 (best known).

**Best program:** worker 2, cycle 8, "Contention-Priced Construction With Protected Iterated Ejection"
(`results/aeossp/programs/best_w2_cycle8.py`), dev 76.63 (59% of the start-to-MILP gap).

| Test set (5 missions) | Mean N | Mean WCR |
|---|---|---|
| Exact MILP (best known) | 76.43 | 0.767 |
| MWIS (benchmark solver) | 75.95 | 0.758 |
| **Muse** | **75.40** | 0.740 |
| Start program | 73.28 | 0.703 |
| Codex CLI + GPT-5.4 (paper's best agent) | 72.91 | - |
| greedy_lns (benchmark solver) | 71.63 | - |

On the 23 sealed missions Muse beat the start on 23 of 23 (mean +1.99 N where both are valid, minimum +1.44). On the hard
mission (test_hard case_0001: 40 satellites, 3,995 requests) the start empties three batteries (13:07:25, 13:24:05 and
13:54:25 UTC) and scores 0; Muse's plan is valid (N 77.92, lowest battery 15.74 Wh, WCR 0.830, 3,311 photos).

Caveats: the paper's agents had to compute geometry themselves (our packs pre-compute it); Muse's program has a 60 s limit
while MWIS is unlimited; Muse is below MWIS on all 13 sealed missions where MWIS was run
(8 test and train missions, 5 hard missions).
