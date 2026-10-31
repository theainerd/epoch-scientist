#!/usr/bin/env bash
# Run one AstroAgentBench reference solver on one mission and verify it with the official verifier.
# Usage: yardsticks/run_solver.sh <family> <solver> <split> <case>   e.g. revisit_constellation j2_rgt_set_cover test case_0001
set -u
F=$1; S=$2; SP=$3; C=$4
HERE=$(cd "$(dirname "$0")" && pwd); ROOT=$(cd "$HERE/.." && pwd)
AAB=${AAB_DIR:-$ROOT/external/AstroAgentBench}; WORK=${MS_WORK:-$ROOT/work}
export MPLCONFIGDIR=${MPLCONFIGDIR:-/tmp/mpl}
export SOLVER_PYTHON=${SOLVER_PYTHON:-$(command -v python)}
OUT=$WORK/yardsticks/$F/$S/$SP/$C; mkdir -p "$OUT"; CASE=benchmarks/$F/dataset/cases/$SP/$C
cd "$AAB"
# The shim turns process pools into thread pools (needed in sandboxes without POSIX semaphores; harmless elsewhere).
export PYTHONPATH="$HERE/shim"
t0=$(date +%s); bash solvers/$F/$S/solve.sh $CASE "" "$OUT" > "$OUT/solve.log" 2>&1; rc=$?; t1=$(date +%s)
export PYTHONPATH="$AAB"
python -m benchmarks.$F.verifier.run $CASE "$OUT/solution.json" > "$OUT/verify.out" 2> "$OUT/verify.err"; t2=$(date +%s)
echo "$F $S $SP $C solve_rc=$rc solve_s=$((t1-t0)) verify_s=$((t2-t1))"
