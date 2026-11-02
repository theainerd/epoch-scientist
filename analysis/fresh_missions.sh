#!/usr/bin/env bash
# Fresh-mission generalisation test (see results/revisit/fresh_missions/README.md). Needs `make fetch`.
# Reruns the start program, Muse's frozen best program and the expert solver j2_rgt_set_cover on the 20 fresh missions
# and the cyclone-watch mission, then scores everything.   Usage: bash analysis/fresh_missions.sh   (JOBS=2 by default)
# Time: start + Muse about 10 min in total; expert about 8-18 min per mission (about 2 h for all 21 with JOBS=2).
# Optional: regenerate the fresh missions with the benchmark generator and compare: REGEN=1 bash analysis/fresh_missions.sh
set -u
ROOT=$(cd "$(dirname "$0")/.." && pwd); AAB=${AAB_DIR:-$ROOT/external/AstroAgentBench}; WORK=${MS_WORK:-$ROOT/work}
R=$ROOT/results/revisit/fresh_missions; O=$WORK/fresh_missions; mkdir -p "$O"; export MPLCONFIGDIR=${MPLCONFIGDIR:-/tmp/mpl}
if [ "${REGEN:-0}" = 1 ]; then
  (cd "$AAB" && PYTHONPATH="$AAB" python -m benchmarks.revisit_constellation.generator.run "$R/splits_fresh.yaml" \
     --output-dir "$O/regenerated" --download-dir "$O/source_data")
  python - "$R" "$O/regenerated" <<'P'
import sys, json
r, g = sys.argv[1:]
same = all(json.load(open(f'{r}/cases/test/case_{i:04d}/mission.json')) == json.load(open(f'{g}/cases/test/case_{i:04d}/mission.json')) for i in range(1, 21))
print('regenerated missions identical to the repo copy:', same)
P
fi
CASES=$(python -c "print(','.join(f'case_{i:04d}' for i in range(1, 21)))")
for P in "muse:$ROOT/results/revisit/programs/best_w2_cycle10.py" "start:$ROOT/tasks/revisit/program_0/src/program.py"; do
  N=${P%%:*}; F=${P#*:}
  DATA_DIR=$R python "$ROOT/tasks/revisit/evaluate.py" --program_path "$F" --results_dir "$O/$N" --split test --cases "$CASES" --quiet
  DATA_DIR=$R/cyclone python "$ROOT/tasks/revisit/evaluate.py" --program_path "$F" --results_dir "$O/${N}_cyclone" --split test --cases case_0001 --quiet
done
one() {  # $1 = mission set dir, $2 = case, $3 = output dir
  CASE=$1/cases/test/$2; OUT=$3/$2; mkdir -p "$OUT"
  grep -q '"is_valid"' "$OUT/verify.out" 2>/dev/null && return
  (cd "$AAB" && PYTHONPATH="$ROOT/yardsticks/shim" bash solvers/revisit_constellation/j2_rgt_set_cover/solve.sh "$CASE" "" "$OUT" > "$OUT/solve.log" 2>&1
   PYTHONPATH="$AAB" python -m benchmarks.revisit_constellation.verifier.run "$CASE" "$OUT/solution.json" > "$OUT/verify.out" 2> "$OUT/verify.err")
  echo "expert done: $2"
}
export -f one; export ROOT AAB
{ for i in $(seq 1 20); do printf '%s case_%04d %s\n' "$R" "$i" "$O/j2"; done; printf '%s case_0001 %s\n' "$R/cyclone" "$O/j2_cyclone"; } |
  xargs -P "${JOBS:-2}" -L 1 bash -c 'one "$0" "$1" "$2"'
python "$ROOT/analysis/score_fresh_missions.py" "$O"
