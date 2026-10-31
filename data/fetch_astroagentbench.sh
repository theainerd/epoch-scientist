#!/usr/bin/env bash
# Download AstroAgentBench (MIT licence, OpenMOSS-Team) into external/AstroAgentBench as a tarball (no git needed).
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd); DEST=${AAB_DIR:-$ROOT/external/AstroAgentBench}; REF=${AAB_REF:-main}
if [ -d "$DEST/benchmarks" ]; then echo "already present: $DEST"; exit 0; fi
mkdir -p "$DEST"
curl -fsSL "https://github.com/Mtrya/AstroAgentBench/archive/refs/heads/$REF.tar.gz" | tar xz -C "$DEST" --strip-components=1
echo "AstroAgentBench -> $DEST"; ls "$DEST/benchmarks"
