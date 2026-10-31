#!/usr/bin/env bash
# Reproduction smoke test. Revisit always runs; AEOSSP runs when its train world pack exists (build: SPLITS=train make pack-aeossp).
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd); WORK=${MS_WORK:-$ROOT/work}; AAB=${AAB_DIR:-$ROOT/external/AstroAgentBench}; T=$WORK/smoke; mkdir -p "$T"
check() { python - "$1" "$2" "$3" <<'P'
import json, sys; m = json.load(open(sys.argv[1])); got = m['combined_score']; want = float(sys.argv[2])
ok = abs(got - want) < 1e-4; print(f"{'PASS' if ok else 'FAIL'}  {sys.argv[3]}: {got:.6f} (expected {want:.6f})"); sys.exit(0 if ok else 1)
P
}
export DATA_DIR=$AAB/benchmarks/revisit_constellation/dataset
python "$ROOT/tasks/revisit/evaluate.py" --program_path "$ROOT/tasks/revisit/program_0/src/program.py" --results_dir "$T/revisit_p0_dev" --quiet > /dev/null
check "$T/revisit_p0_dev/metrics.json" 69.820818 "Revisit start program, dev missions"
python "$ROOT/tasks/revisit/evaluate.py" --program_path "$ROOT/results/revisit/programs/best_w2_cycle10.py" --results_dir "$T/revisit_best_t7" --split train --cases case_0007 --quiet > /dev/null
check "$T/revisit_best_t7/metrics.json" 85.789474 "Revisit Muse best, sealed train case_0007"
if [ -d "$WORK/aeossp/pack/worlds/train/case_0007" ]; then
  export DATA_DIR=$WORK/aeossp/pack
  python "$ROOT/tasks/aeossp/evaluate.py" --program_path "$ROOT/tasks/aeossp/program_0/src/program.py" --results_dir "$T/aeossp_p0_dev" --quiet > /dev/null
  check "$T/aeossp_p0_dev/metrics.json" 74.926186 "AEOSSP start program, dev missions"
else echo "SKIP  AEOSSP (no world pack; run: SPLITS=train make pack-aeossp)"; fi
