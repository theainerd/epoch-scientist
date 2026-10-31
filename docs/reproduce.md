# Reproduce

## Score the shipped programs (laptop, no Muse needed)
```bash
conda env create -f environment.yml && conda activate muse-scientist
make fetch check-verifiers smoke
make sealed-revisit                       # ~10 min
SPLITS="train test test_easy test_hard test_horizon_2022" make pack-aeossp && make sealed-aeossp
make yardstick-revisit                    # optional, slow (~30 min per mission)
make videos                               # after the sealed runs
```

## Run a new blind search with Muse (Kaggle)
1. `make fetch pack-aeossp` (AEOSSP only), then `make kaggle-datasets KAGGLE_USER=<you>`. Put the brahe 1.8.0
   manylinux wheels (cp311, cp312) into `work/kaggle/<name>/wheels/`, then `kaggle datasets create -p work/kaggle/<name> --dir-mode zip`.
2. Copy `runner/kaggle/run_<problem>.py` to a new folder as `run.py`, with `runner/kaggle/kernel-metadata.example.json`
   (set your id and dataset). `kaggle kernels push -p <folder>` runs a free PREFLIGHT (no secrets attached): it installs the
   toolchain, downloads AI-Scientist-v3, applies `runner/patches/meta_provider.patch`, and checks that the harness scores
   `program_0` exactly (gate).
3. In the Kaggle editor, attach the secrets `MODEL_API_KEY` (Meta Model API key) and `WANDB_API_KEY`, then Save & Run All.
   Settings (env vars or the defaults at the top of run.py): `AISCI_MODEL` (meta/muse-wonder-1.0), `AISCI_CYCLES` (20),
   `AISCI_WORKERS` (2), `AISCI_BUDGET_USD` (40).
4. Download the output, extract `results.tar.gz` without `node_modules`, then run `analysis/extract_runs.py` and
   `analysis/sealed_eval.sh` on the best program (`best_program_manifest.json`).

Lessons that cost us runs: keep every task file at the top level (the harness copies only top-level files); raise OpenCode's
bash timeout (the runner sets 600 s); do not push the notebook during a paid run (every push starts a new run).
