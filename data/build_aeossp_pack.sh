#!/usr/bin/env bash
# Build the AEOSSP world pack: pre-computed observation opportunities for every mission (work/aeossp/pack/worlds/<split>/<case>),
# plus a link to the official mission files (work/aeossp/pack/cases). About 1-2 min per mission.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd); AAB=${AAB_DIR:-$ROOT/external/AstroAgentBench}; WORK=${MS_WORK:-$ROOT/work}
PACK=$WORK/aeossp/pack; mkdir -p "$PACK/worlds"; ln -sfn "$AAB/benchmarks/aeossp_standard/dataset/cases" "$PACK/cases"
for sp in ${SPLITS:-train test test_easy test_hard test_horizon_2022}; do
  for c in $(ls "$PACK/cases/$sp"); do
    [ -f "$PACK/worlds/$sp/$c/world.npz" ] && continue
    python "$ROOT/data/build_aeossp_worlds.py" $sp $c
  done
done
echo "pack: $PACK"
