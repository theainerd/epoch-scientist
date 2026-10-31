# Phase 0: choosing the second problem (30 Oct 2026)

Measured on the Mac with the official AstroAgentBench verifiers and the published reference solvers (unchanged code;
process pools replaced by thread pools through a startup shim, because the sandbox forbids process pools).

## Measured on train missions 1-2

| Family | Mission | Solver A | Solver B | Solver time | Verifier time |
|---|---|---|---|---|---|
| Revisit (requirement / satellite cap) | train 1 (8 h / 16) | J2 RGT set cover: requirement met, 15 satellites | RGT/APC: missed (14.6 h), 16 satellites | 6-8 min | 18 s |
| | train 2 (6 h / 20) | J2 RGT set cover: requirement met, 20 satellites | RGT/APC: missed (12.0 h), 20 satellites | 7-8 min | 14-19 s |
| Relay (served fraction / worst demand) | train 1 | MCLP-TEG: 0.941 / 0.633, 0 relays added | UMCF-SRR: 0.928 / 0.556, 0 added | 1-2 min | 5 s |
| | train 2 | MCLP-TEG: 0.864 / 0.250, 6 added | UMCF-SRR: 0.742 / 0.244, 5 added | 1-2 min | 11 s |

## Paper, test missions (Table 15, native metrics)

| Family | Best published solver | Best coding agent | Room above the best solver |
|---|---|---|---|
| Revisit: mean satellites (revisit gap about 6.8 h for all) | 17.2 | 11.4 (Claude Code + Opus 4.6) | large: an agent used 34% fewer satellites |
| Relay: served fraction | 0.933 | 0.935 (Codex + GPT-5.4; full service on 1 of 5) | narrow: 0.93 -> 1.00 |

## Verdict
Revisit Constellation passes the gate: search-limited (a better design directly needs fewer satellites), the best published
solver needs nearly every allowed satellite, a fast verifier (about 20 s per mission), and train/test splits exist.
Relay Constellation is the backup: very fast, but the room is narrow and full service may be impossible on some missions.
The paper's 0-100 anchors for these families are not published, so results are reported in native metrics
(requirement met, then number of satellites), exactly as in the paper's Table 15.
