# Runner (Kaggle)

* `kaggle/run_aeossp.py`, `kaggle/run_revisit.py`: the exact notebooks used for the two runs. They install Node 22,
  OpenCode 1.18.29 and headless-cli, download the AI-Scientist-v3 fork, apply the Meta provider patch, disable web tools,
  add the task packages to the pipeline venv, run a harness-path gate on `program_0`, ping the model, run a 150 s
  bash-timeout gate, then start `agsci run` with a budget guard and W&B monitoring.
* `patches/meta_provider.patch` (Apache-2.0): adds the Meta Model API as an OpenCode provider in AI-Scientist-v3.
* `kaggle/kernel-metadata.example.json`: template; set `id` and `dataset_sources` to your own.
