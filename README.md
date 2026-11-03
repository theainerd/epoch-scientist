# Epoch Scientist

**Agentic research with Meta Muse Wonder.** Give it a problem as a prompt and a verifier. Meta Muse Wonder proposes ideas,
writes the code, tests it and keeps only what scores better. We tested it on two satellite problems from AstroAgentBench,
then ran its best program once on held-out missions and compared it with expert solvers.

> **Meta Global AI Developer Hackathon 2026 · Push the Frontier · Indie track**<br>
> **Built this week (26 Oct – 4 Nov 2026):** all code, task packs, runs, tests and analysis in this repo. It uses open-source
> tools: AI-Scientist-v3 (Sakana AI), OpenCode and AstroAgentBench.<br>
> **Meta model:** Meta Muse Wonder (`meta/muse-wonder-1.0`) does every research step.<br>
> **Open weights:** Muse Spark on Baseten (meta-models/muse-spark-open) ran the same setup on a third problem.<br>
> **Bonus prize:** Best Agentic Use-Case

<p align="center"><a href="https://youtu.be/866FbIutjNQ"><img src="media/video/epoch_scientist_explainer.gif" width="900" alt="Highlights of the 2-minute Epoch Scientist explainer: the problem, 20 vs 15 vs 10 satellites, 23 of 23 missions, 67% of the gap"></a></p>

<p align="center"><sub>Held-out Revisit mission: start program 20 satellites · expert solver 15 · <b>Meta Muse Wonder 10</b>, every place on time.<br>
On 20 fresh missions made after the search, Muse's unchanged program beat the expert solver on <b>18 of 20</b>.<br>
▶ <a href="https://youtu.be/866FbIutjNQ">Watch the full 2-minute explainer on YouTube</a>, narrated (click the preview).</sub></p>

## What we claim

Every row uses one metric on one fixed set of missions Muse never saw during the search.

| Problem, missions, metric | Start program | **Meta Muse Wonder** | Expert solver |
|---|---|---|---|
| Satellite photo scheduling (AEOSSP): 5 test missions, mean score | 73.28 | **75.40** | MWIS 75.95, MILP 76.43 |
| Constellation design (Revisit): 5 held-out missions with the expert run (train 5-9), mean score | 69.04 | **78.54** | j2 set cover 72.17 |
| Revisit: same 5 missions, mean satellites | 19.6 | **14.4** | j2 set cover 18.0 |
| Revisit: 20 fresh missions made after the search (new generator seed), mean score | 63.10 | **76.40** | j2 set cover 72.45 |
| Revisit: same 20 fresh missions, mean satellites | 18.8 | **14.9** | j2 set cover 17.0 |

1. **Muse beat the expert constellation solver, also on missions nobody had seen.** It scored higher on 4 of 5 held-out missions,
   with 20% fewer satellites. Then we made 20 fresh missions with the benchmark's own generator and a new seed, and wrote the
   rules down before running the expert. Muse's unchanged program beat the expert on **18 of 20** (sign test p = 0.0004), with
   12% fewer satellites; on 15 of 20 it used fewer satellites and met at least as many targets
   ([test and rules](results/revisit/fresh_missions/README.md)).
2. **Muse closed 67% of the gap to the best-known schedule.** That is the gap from the start program to the MILP reference on
   the test missions. It also beat the start program on **23 of 23** held-out missions, and its plans stayed valid on all 6
   where the start plan was invalid. On the 5 hard missions it lands between the two published solvers (MWIS 79.25,
   **Muse 78.54**, greedy_lns 75.15; [table](results/aeossp/hard_missions_yardsticks.csv)).
3. **Muse debugged its own science.** On Revisit, it traced a score of 0 to a sign error in its own camera-angle check, fixed it,
   and went on to its best design. It named its best ideas itself: "Geometry-Diverse Constructive Growth" and
   "Contention-Priced Construction With Protected Iterated Ejection". The research process mattered: 3 of its 4 first attempts scored
   below the start program, and the scores climbed from there.
4. **Muse wrote its own code.** Its best programs (800-1,300 lines) share 0.2-0.4% of their code sequences with the
   benchmark's reference solvers, close to the 0.0-0.1% they share with solvers for an unrelated problem; a renamed copy of a
   solver scores 99.4% ([check](analysis/code_originality.py), [results](results/code_originality.csv)).

<p align="center"><img src="media/stills/search_progress.png" width="900" alt="Score per attempt for both problems: start program, Muse workers, expert solver"></p>

The same setup also runs with the open-weight **Muse Spark on Baseten**: on a third problem (space-probe routes) it raised the practice score from 100 to 139.5 in 164 min. The best program was not kept, so it has no held-out test (record and limits: [results/wandb/trajectory_233j2q1l/](results/wandb/trajectory_233j2q1l/)).

## What we do not claim

* **Not the best scheduler.** MWIS scores above Muse on all 13 held-out AEOSSP missions where it ran, including the 5 hard missions
  (79.25 vs 78.54). On those 5 missions the start program is invalid (score 0), so the large gain there is over our own start
  program, not over the experts.
* **Not the fewest satellites.** On the 5 Revisit test missions, the best published agent uses 11.4 satellites, Muse 16.0 and the
  benchmark's reference solver 17.2; that solver meets every target, while Muse misses 5 targets on one mission.
  This is not like-for-like: those agents planned each mission directly with hours of time, while Muse writes one general
  program that solves any mission in 200 s on one CPU thread.
* **Not every target on every mission.** All 11 held-out Revisit plans are valid; 9 meet every target, and 2 miss some. On the
  20 fresh missions the expert meets every target on 17, Muse on 16. On a hand-made "cyclone watch" mission (30 cyclone-prone
  coastal cities, a photo every 6 h, 20 satellites) the expert meets every deadline and Muse misses 3 cities.
* **Not one-of-a-kind discovery.** Each problem had one run and one seed. Blind means no look-ups, not an untrained model, and
  Muse mostly recombined known optimisation methods.

## Quick start (no key, about 10 minutes)

```bash
conda env create -f environment.yml && conda activate epoch-scientist
make fetch check-verifiers smoke     # scores of the start and best programs reproduce exactly
bash demo/show_task.sh               # what Muse Wonder gets
python demo/replay_notebook.py results/revisit/notebook/aisci-revisit-blind-run.log --cost results/revisit/notebook/cost_summary.json
```

A full run takes about 2 hours, so the last command replays the real log of one run.

## Run it on your machine

```bash
cp .env.example .env                                      # add your Meta Model API key
python runner/local/run_local.py --task revisit --check   # free check, no model calls
python runner/local/run_local.py --task revisit           # full run: about 2 h, about $30
```

The check must print `HARNESS-PATH BASELINE 69.82… OK`. The full run stops by itself at $36 (`--budget-usd`, default 40).
Results go to `work/local/out/results.tar.gz`.

| Needs | |
|---|---|
| Machine | Linux (macOS: the harness needs `/proc`, use a Linux container), 4+ CPU cores, 16 GB RAM, 3 GB free disk, no GPU (our runs peaked at about 12 GB) |
| Software | conda (Python 3.12), git, curl; the runner installs everything else under `work/local` |
| Account | Meta Model API key, for a full run only |

## Bring your own problem

Anything a program can be scored on works. Make one folder, using `tasks/revisit/` as the example:

```
tasks/my_problem/
  task.md                    the problem in plain words, the program contract, the score
  evaluate.py                your verifier
  program_0/src/program.py   a simple start program (copy program_spec.toml from tasks/revisit/program_0/)
  idea_example.json          copy from tasks/revisit/ and edit
  rubrics_example.json       copy from tasks/revisit/ and edit
  requirements.txt
```

`python evaluate.py --program_path <program.py> --results_dir <dir>` must write `metrics.json` with `combined_score`
(higher is better). Keep all files at the top level, and keep your test data out of `--data-dir`.

```bash
python runner/local/run_local.py --task-dir tasks/my_problem --data-dir <dev data> --check
```

## Use it with your coding agent

Paste one prompt into your coding agent (Claude Code, Codex, Cursor, OpenCode) in a clone of this repo.

**1. Run this project**

```text
Set up and verify this repo on my machine, following README.md "Quick start" and "Run it on your machine".
Run each command in order. Stop at the first failure and show me the last 30 lines.
Expected: `make smoke` reproduces the scores in README.md, and the check prints "HARNESS-PATH BASELINE 69.82... OK".
Do not start the full run (about 2 h, about $30) until I say so. Never print or commit MODEL_API_KEY.
Finish with a table: command, result, time.
```

**2. Try it on your own problem**

```text
Help me use this repo's agentic research on my own problem. Follow README.md "Bring your own problem",
with tasks/revisit/ as the example.

Problem: <the goal, in 2-3 sentences>
Data:    <path, and which part to keep for the final test>
Score:   <what makes one answer better than another>

1. Ask me if the goal, the data split or the score is unclear. Do not guess the score.
2. Build tasks/<name>/. Put only development data in the --data-dir folder.
3. Score program_0 by hand (one evaluation should take minutes), then run the free check until it prints "OK".
4. Ask me before the full run; it costs money.
5. After the run, score the best program once on the test data. Report start, best and test scores.
   Do not change evaluate.py after the run. Never commit .env, keys or the test data.
```

## How it works

<p align="center"><img src="assets/discovery_loop.png" width="900" alt="What Meta Muse Wonder gets, the agentic research cycle, and the held-out test"></p>

**Meta Muse Wonder** (`meta/muse-wonder-1.0`) is the intelligence layer that drives all the reasoning: it proposes each idea,
writes and fixes the code, and learns from the scores. The locked scorer decides what is kept. Details:
[method](docs/method.md), [all 40 ideas](docs/ideas.md), [all results](docs/results.md).

Run logs: both runs were logged live to Weights & Biases; the full records are exported in [results/wandb/](results/wandb/).

<p align="center"><img src="media/stills/wandb_runs.png" width="760" alt="Weights & Biases run logs: best and last score, attempts over time"></p>

## The benchmark

[AstroAgentBench](https://github.com/Mtrya/AstroAgentBench) gives an agent the mission files and tools, then an independent
verifier scores its plan. We use two of its problems: [AEOSSP](docs/problem_aeossp.md) and
[Revisit](docs/problem_revisit.md). For more details, see the [paper](https://arxiv.org/abs/2601.11354) and
[our notes](docs/astroagentbench.md).

<p align="center"><img src="assets/astroagentbench_overview.png" width="700" alt="AstroAgentBench: problem setup, agent planning, external evaluation"></p>

## More checks

```bash
python analysis/code_originality.py       # Muse Wonder's code vs the benchmark's reference solvers
python analysis/score_fresh_missions.py   # fresh-mission test from the stored plans (full rerun: bash analysis/fresh_missions.sh)
```

Full held-out evaluation and a new blind search: [docs/reproduce.md](docs/reproduce.md).

## Watch

* [2-minute explainer on YouTube](https://youtu.be/866FbIutjNQ): the whole project in one narrated video ([MP4 in the repo](media/video/epoch_scientist_explainer.mp4), [captions](media/video/epoch_scientist_explainer.srt)).
* [Held-out Revisit mission](media/video/revisit_before_after.mp4): 20 → 10 satellites, every place on time.
* [Hard AEOSSP mission](media/video/aeossp_before_after.mp4): the start empties 3 batteries; Muse stays valid.
* [How Muse searches](media/video/search_revisit.mp4): a replay of the real run.

## Credits and licence

Our code: MIT ([LICENSE](LICENSE)). AstroAgentBench (MIT, OpenMOSS-Team) supplies the verifier code and mission files. The runner
uses OpenCode and AI-Scientist-v3 (Apache-2.0, Sakana AI), patched with `runner/patches/meta_provider.patch`. See [NOTICE.md](NOTICE.md).
