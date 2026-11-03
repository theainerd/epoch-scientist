# Demo scripts

The demo video shows only real output. It is not a live run: a full discovery run takes 1 h 49 min and cost $29.10 (Meta-reported), so the video replays the recorded logs with these scripts. The backdrop of the video is the real plan Muse's program made for mission seed 20261103 (17 satellites), propagated with the verifier's propagator.

| Script | What it shows | Run time |
|---|---|---|
| `bash demo/show_task.sh` | The input Muse gets: the task folder, the goal, the verifier identity check, the start program | about 1 s |
| `python demo/replay_agent.py results/revisit/agent_logs/cycle10_worker2_agent_opencode_20261030_180258.log` | Meta Muse Wonder at work: the real OpenCode agent log of the attempt that wrote `results/revisit/programs/best_w2_cycle10.py` (30 Oct 2026, 6.3 min, 40 model calls, $1.007 as reported by the Meta Model API) | about 1 s |
| `python demo/replay_notebook.py results/revisit/notebook/aisci-revisit-blind-run.log --cost results/revisit/notebook/cost_summary.json` | The real Kaggle notebook of the Revisit discovery run (30 Oct 2026): setup, harness check (69.82), a live Meta Model API call, then 1 h 37 min of search with heartbeats every 2 min (attempts scored, best score, Meta-reported cost), the W&B summary (20 attempts, best 77.82) and `cost_summary.json` (40 billed events, $29.10). Total notebook time 1:49:29 | about 1 s |
| `python demo/live_proof.py <seed>` | A brand-new mission from the AstroAgentBench generator, planned by the start program, Muse's frozen program and the expert solver j2, all checked by the official verifier | 8–18 min (the expert solver takes most of it); `--no-expert` takes about 2 min |

Notes on the logs:
- `results/revisit/notebook/aisci-revisit-blind-run.log` is the Kaggle kernel log as downloaded. One change: the name of a private W&B workspace is replaced by `private-workspace`. The replay also hides those W&B lines behind a visible `[... skipped ...]` marker.
- The runner labels a run with an API key attached as `mode SMOKE`. This run is the full 20-cycle discovery run, not a smoke test.
- The replays shorten long lines (they end in `...`) and summarise heartbeat JSON as its key fields. Nothing else is changed.

`live_proof.py` needs the benchmark (`make fetch`, or `AAB_DIR=<path to AstroAgentBench>`).

Recorded result for seed 20261103 (25 places, 6 h, at most 20 satellites), 2 Nov 2026:

| Program | Satellites | On time | Score | Planned in |
|---|---|---|---|---|
| Start program | 20 | 25/25 | 70.0 | 25 s |
| Muse (Meta Muse Wonder) | 17 | 25/25 | 74.7 | 17 s |
| Expert solver (j2) | 16 | 25/25 | 76.3 | 429 s |

On this one mission the expert wins by one satellite. On the 20 pre-registered fresh missions (`results/revisit/fresh_missions/`), Muse's program wins 18 of 20.
