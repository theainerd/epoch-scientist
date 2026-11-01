# Weights & Biases run logs

Both blind Muse Wonder runs were logged live to Weights & Biases from the Kaggle notebook. The W&B workspace cannot be made
public, so the full run records are exported here, unchanged, with `analysis/export_wandb.py`. The charts are redrawn by
`analysis/plot_wandb_runs.py` (`media/stills/wandb_runs.png`).

| Folder | W&B run | Rows logged | Result |
|---|---|---|---|
| `aeossp_bcw9vydb/` | aeossp-blind-muse-wonder-1.0-1030-0829 | 51 (every 2 min, 113 min) | 20 attempts scored, 0 failed, best dev 76.63 |
| `revisit_z3vvh4ce/` | revisit-blind-muse-wonder-1.0-1030-1632 | 46 (every 2 min, 105 min) | 20 attempts scored, 0 failed, best dev 77.82 |

Files in each folder:

* `run_info.json`: run name, state, start and last heartbeat time.
* `config.json`: run configuration (task, model `meta/muse-wonder-1.0`, cycles, workers).
* `wandb-summary.json`: final values of every metric.
* `history.jsonl`: every logged row (best and last score, attempts, per-metric details of the best program, API cost).
* `system_metrics.jsonl`: CPU, memory, disk and network of the Kaggle machine, sampled by W&B.

Not included: the console log `output.log` and `requirements.txt` (W&B stores them in file storage, not in the API export).
