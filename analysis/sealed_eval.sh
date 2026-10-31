#!/usr/bin/env bash
# Score programs on the SEALED missions (never given to the agent) with the same evaluator the run used.
# Usage: analysis/sealed_eval.sh aeossp|revisit <tag> <program.py>     outputs: work/sealed/<problem>/<tag>_<split>/metrics.json
set -euo pipefail
P=$1; TAG=$2; PROG=$3; ROOT=$(cd "$(dirname "$0")/.." && pwd); WORK=${MS_WORK:-$ROOT/work}; O=$WORK/sealed/$P; mkdir -p "$O"
AAB=${AAB_DIR:-$ROOT/external/AstroAgentBench}
if [ "$P" = aeossp ]; then
  export DATA_DIR=$WORK/aeossp/pack
  python "$ROOT/tasks/aeossp/evaluate.py" --program_path "$PROG" --results_dir "$O/${TAG}_train" --split train --cases case_0008,case_0009,case_0010 --quiet
  for sp in test test_easy test_hard test_horizon_2022; do python "$ROOT/tasks/aeossp/evaluate.py" --program_path "$PROG" --results_dir "$O/${TAG}_$sp" --split $sp --cases $(ls "$DATA_DIR/worlds/$sp" | paste -sd, -) --quiet; done
else
  export DATA_DIR=$AAB/benchmarks/revisit_constellation/dataset
  python "$ROOT/tasks/revisit/evaluate.py" --program_path "$PROG" --results_dir "$O/${TAG}_train" --split train --cases case_0005,case_0006,case_0007,case_0008,case_0009,case_0010 --quiet
  python "$ROOT/tasks/revisit/evaluate.py" --program_path "$PROG" --results_dir "$O/${TAG}_test" --split test --cases case_0001,case_0002,case_0003,case_0004,case_0005 --quiet
fi
for f in "$O"/${TAG}_*/metrics.json; do python -c "import json,sys;m=json.load(open('$f'));print('$f'.split('/')[-2], round(m['combined_score'],3), m.get('n_valid'), '/', m.get('n_cases'))"; done
