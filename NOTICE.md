# Third-party components

| Component | Where | Licence |
|---|---|---|
| AstroAgentBench verifiers (`aeossp_standard`, `revisit_constellation`), merged into one file each without code changes | `tasks/aeossp/aab_verifier.py`, `tasks/revisit/revisit_verifier.py` | MIT, Copyright (c) 2026 OpenMOSS-Team |
| AstroAgentBench missions, solvers, land outline (`ne_110m_land.geojson`, Natural Earth, public domain) | downloaded to `external/` by `data/fetch_astroagentbench.sh` | MIT / public domain |
| Meta provider patch for AI-Scientist-v3 | `runner/patches/meta_provider.patch` (also embedded in `runner/kaggle/run_*.py`) | Apache-2.0 (derivative of AI-Scientist-v3, Sakana AI) |
| AI-Scientist-v3, OpenCode, headless-cli | downloaded at run time by the Kaggle runner | Apache-2.0 / MIT (see upstream) |
| brahe 1.8.0 (astrodynamics) | pip dependency | MIT |

AstroAgentBench MIT licence text: Permission is hereby granted, free of charge, to any person obtaining a copy of this
software and associated documentation files (the "Software"), to deal in the Software without restriction, ... The above
copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
(Full text: https://github.com/Mtrya/AstroAgentBench/blob/main/LICENSE)

"Meta" and "Muse" are trademarks of Meta Platforms, Inc.; they are used here only to name the model that was used.
