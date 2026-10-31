#!/usr/bin/env bash
# Hidden yardstick for Revisit: run the benchmark's j2_rgt_set_cover solver on every mission that has no verified result yet.
# Two missions at a time (about 25-40 min each on an 8 GB laptop).
HERE=$(cd "$(dirname "$0")" && pwd); ROOT=$(cd "$HERE/.." && pwd); WORK=${MS_WORK:-$ROOT/work}
B=$WORK/yardsticks/revisit_constellation/j2_rgt_set_cover; todo=""
for c in train/case_0001 train/case_0002 train/case_0003 train/case_0004 train/case_0005 train/case_0006 train/case_0007 train/case_0008 train/case_0009 train/case_0010 test/case_0001 test/case_0002 test/case_0003 test/case_0004 test/case_0005; do
  grep -q '"is_valid"' "$B/$c/verify.out" 2>/dev/null || todo="$todo $c"
done
echo "todo:$todo"
printf '%s\n' $todo | xargs -P ${JOBS:-2} -I{} bash -c 'bash '"$HERE"'/run_solver.sh revisit_constellation j2_rgt_set_cover $(dirname {}) $(basename {})'
echo ALL_DONE
