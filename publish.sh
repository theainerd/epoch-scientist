#!/usr/bin/env bash
# Create the git repository and push it to GitHub.
# Usage:  ./publish.sh <github-user>                              (with the GitHub CLI `gh`: creates the repo and pushes)
#         ./publish.sh git@github.com:<user>/muse-scientist.git    (existing empty repo: adds the remote and pushes)
set -euo pipefail
cd "$(dirname "$0")"
TARGET=${1:?give your GitHub user name or a remote URL}
REPO=muse-scientist
# work/, external/ and __pycache__/ are listed in .gitignore, so they stay on disk but are not committed.
if [ ! -d .git ]; then
  git init -q -b main
  git add -A
  git commit -q -m "Muse Scientist: Muse Wonder + OpenCode + AI-Scientist-v3 on AstroAgentBench (AEOSSP, Revisit Constellation)"
fi
if [[ "$TARGET" == *:* || "$TARGET" == http* ]]; then
  git remote add origin "$TARGET" 2>/dev/null || git remote set-url origin "$TARGET"
  git push -u origin main
elif command -v gh >/dev/null 2>&1; then
  gh repo create "$TARGET/$REPO" --public --source . --remote origin --push \
     --description "Meta Muse Wonder + OpenCode + AI-Scientist-v3: an AI scientist that improves satellite mission planners on AstroAgentBench"
else
  echo "GitHub CLI not found. Create an empty repo named $REPO on github.com, then run:"
  echo "  ./publish.sh git@github.com:$TARGET/$REPO.git"
fi
