# Third-party components

| Component | Where | Licence |
|---|---|---|
| AstroAgentBench verifiers (`aeossp_standard`, `revisit_constellation`), merged into one file each without code changes | `tasks/aeossp/aab_verifier.py`, `tasks/revisit/revisit_verifier.py` | MIT, Copyright (c) 2026 OpenMOSS-Team |
| AstroAgentBench missions, solvers, land outline (`ne_110m_land.geojson`, Natural Earth, public domain) | downloaded to `external/` by `data/fetch_astroagentbench.sh` | MIT / public domain |
| Meta provider patch for AI-Scientist-v3 | `runner/patches/meta_provider.patch` (also embedded in `runner/kaggle/run_*.py`) | Apache-2.0 (derivative of AI-Scientist-v3, Sakana AI) |
| AI-Scientist-v3, OpenCode, headless-cli | downloaded at run time by the Kaggle runner | Apache-2.0 / MIT (see upstream) |
| brahe 1.8.0 (astrodynamics) | pip dependency | MIT |

Full licence texts are in [LICENSES/](LICENSES/):

* [AstroAgentBench-MIT.txt](LICENSES/AstroAgentBench-MIT.txt): MIT, Copyright (c) 2026 OpenMOSS-Team. It covers the two verifier
  files copied into `tasks/` (kept byte-identical to the official code, so the notice is kept here, not in the files).
* [AI-Scientist-v3-Apache-2.0.txt](LICENSES/AI-Scientist-v3-Apache-2.0.txt): Apache-2.0 (Sakana AI). It covers
  `runner/patches/meta_provider.patch`. Changes made to AI-Scientist-v3 (Apache-2.0, section 4b), all in that patch: it adds
  a Meta Model API provider config for OpenCode (`configs/opencode/opencode.meta.json`, `configs/opencode/README.md`), lets the
  agent wrappers pass `MODEL_API_KEY` for `meta/*` and `muse*` models (`src/scripts/lib/container_agent.sh`,
  `src/scripts/variant_agent.sh`) and adjusts how the headless agent command is started (`src/investigation/script_runners.py`).

AI-Scientist-v3 is described in: R. T. Lange, L. Grillotti, Y. Yamada, R. Charakorn, D. Ha, "The Agentic Scientist: Orchestrating
Coding Agents for Automated Scientific (Co-)Discovery", arXiv:2610.18933 (2026).

"Meta" and "Muse" are trademarks of Meta Platforms, Inc.; they are used here only to name the model that was used.
