#!/usr/bin/env bash
# Claim 2: the working-precision budget has unit leading slope.
#
# Test parameters:
#   lambda^2=50, N=400, P={50,100,150,200}, seeded zero window 1..5.
#
# Expected result:
#   The fit has |dD/dP - 1| <= 0.005 and R^2 >= 0.999. The current paper
#   reports slope 1.00205 and R^2=0.99994.
set -euo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$REPO_ROOT"

TARGET_DIR=${CARGO_TARGET_DIR:-"$REPO_ROOT/target"}
BIN=${BIN:-"$TARGET_DIR/release/ccm-convergence-rate"}
if [[ ! -x "$BIN" ]]; then
  cargo build --quiet --release --features hp --locked \
    --bin ccm-convergence-rate --target-dir "$TARGET_DIR"
fi

python3 scripts/reproduce.py precision-slope \
  --bin "$BIN" \
  --root-acquisition "${ROOT_ACQUISITION_MODE:-seeded}" \
  --parity-policy "${PARITY_POLICY:-even-sector}" \
  --eigenstate-solver "${EIGENSTATE_SOLVER:-auto}" \
  --research-capture "${RESEARCH_CAPTURE_LEVEL:-research}" \
  --research-sector-eigenpairs "${RESEARCH_SECTOR_EIGENPAIRS:-8}" \
  --first-zero-index "${FIRST_ZERO_INDEX:-1}" \
  --zero-count "${ZERO_COUNT:-5}" \
  --analysis-zero-index "${ANALYSIS_ZERO_INDEX:-1}" \
  --results-dir "${RESULTS_DIR:-"$REPO_ROOT/outputs"}" \
  "$@"
