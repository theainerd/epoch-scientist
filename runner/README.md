# Runner

* `local/run_local.py`: run Epoch Scientist on your own machine (Linux, CPU only; on macOS use a Linux container). `--check` installs the tools
  under `work/local` and runs the free checks (harness reproduces the start score, dry run); without `--check` and with
  `MODEL_API_KEY` set (or in `.env`), it pings the model, runs a 150 s bash-timeout gate, then starts `agsci run` with a
  budget guard. See the README sections "Run it on your machine" and "Bring your own problem".
* `patches/meta_provider.patch` (Apache-2.0): adds the Meta Model API as an OpenCode provider in AI-Scientist-v3.
* `kaggle/`: the exact hosted-notebook scripts used for the two recorded runs (kept for provenance; same steps as `local/`).

Lessons that cost us runs: keep every task file at the top level (the harness copies only top-level files); raise OpenCode's
bash timeout (the runner sets 600 s, because one evaluation takes minutes).
