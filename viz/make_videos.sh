#!/usr/bin/env bash
# Re-render the 4 videos into work/videos. Needs: sealed outputs (make sealed-aeossp sealed-revisit) and ffmpeg.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd); WORK=${MS_WORK:-$ROOT/work}; O=$WORK/videos; mkdir -p "$O"
S=$WORK/sealed/aeossp
python "$ROOT/viz/export_aeossp_replay.py" test_hard case_0001 "$S/p0_test_hard/_cases/case_0001_solution.json" "$S/w2c8_test_hard/_cases/case_0001_solution.json" "$WORK/viz/aeossp"
python "$ROOT/viz/export_revisit_replay.py" train case_0007
python "$ROOT/viz/render_aeossp.py" "$O/aeossp_before_after.mp4"
python "$ROOT/viz/render_revisit.py" "$O/revisit_before_after.mp4"
python "$ROOT/viz/render_search.py" aeossp "$O/search_aeossp.mp4"
python "$ROOT/viz/render_search.py" revisit "$O/search_revisit.mp4"
ls -la "$O"
