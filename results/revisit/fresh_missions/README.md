# Fresh-mission test: does Muse's program still beat the expert on missions nobody has seen?

**Why.** The README claim "Muse beat the expert constellation solver on 4 of 5 sealed missions" rests on 5 missions.
This test uses 20 more, made after the search, so the result cannot come from a lucky mission set.

**What we did (no model calls: Muse's program is frozen code).**
1. Made 30 new missions with the benchmark's own generator and its test-split settings, new seed 314159
   ([splits_fresh.yaml](splits_fresh.yaml)); we use missions 1-20. Largest target-set overlap with any official mission: 0.29.
2. Wrote the rules down before running the expert ([PREREG.md](PREREG.md)): what is reported, and the expectation
   (Muse wins on at least 12 of 20).
3. Ran three programs on each mission: the start program, Muse's best program
   ([best_w2_cycle10.py](../programs/best_w2_cycle10.py), unchanged) and the benchmark's expert solver `j2_rgt_set_cover`.
   The official verifier checked every plan; the score is the task's per-mission rule, as everywhere in the README.

**Result (20 fresh missions).**

| | Start program | **Muse (frozen)** | Expert j2 |
|---|---|---|---|
| Missions where Muse scores higher than the expert | | **18 of 20** | |
| Mean score | 63.10 | **76.40** | 72.45 |
| Mean satellites | 18.8 | **14.9** | 17.0 |
| Missions where every target is met | 5 | 16 | **17** |
| Valid plans | 20 | 20 | 20 |

* Muse used fewer satellites and met at least as many targets as the expert on 15 of 20.
* Mean score difference Muse - expert: +3.95 (95% bootstrap interval 2.46 to 5.35); sign test p = 0.0004.
* By requirement: 6 h missions, Muse wins 8 of 8 (17.5 vs 20.0 satellites); 8 h missions, 10 of 12 (13.2 vs 15.0).
* The expert wins on 2 missions (case_0012, case_0013). Per-mission table: [fresh_missions_results.csv](fresh_missions_results.csv).

**Real-world use case: "cyclone watch".** 30 coastal cities often hit by tropical cyclones (Bay of Bengal, Arabian Sea,
western Pacific, Caribbean, Gulf of Mexico, south-west Indian Ocean, Australia, Fiji), a photo every 6 h for 48 h, at most 20
satellites ([mission](cyclone/cases/test/case_0001/mission.json), built by
[build_cyclone_mission.py](../../../analysis/build_cyclone_mission.py) before any run). Result:
**the expert wins here.** It meets every deadline with 20 satellites (score 70.00); Muse's program and the start program each
miss 3 cities (69.59 and 67.00), although Muse cuts the worst wait from 21.8 h to 9.4 h ([cyclone_results.csv](cyclone_results.csv)).

**Check it.** `python analysis/score_fresh_missions.py` recomputes every number from the stored plans in this folder
(`j2/`, `j2_cyclone/`: expert plans and official verifier output; `muse/`, `start/`: per-mission metrics and plans).
`bash analysis/fresh_missions.sh` reruns everything (about 2 h, mostly the expert solver); `REGEN=1` also regenerates the
missions with the benchmark generator and checks that they are identical to the copies here.
