#!/usr/bin/env bash
# What Epoch Scientist gives Meta Muse Wonder for one problem (Revisit). Usage: bash demo/show_task.sh
cd "$(dirname "$0")/.."
run() { printf '\033[1m$ %s\033[0m\n' "$1"; eval "$1"; echo; }
run "ls tasks/revisit/ | grep -v pycache"
run "python demo/goal.py tasks/revisit/task.md"
run "python data/check_verifier_identity.py"
run "grep -A3 'def solve' tasks/revisit/program_0/src/program.py"
