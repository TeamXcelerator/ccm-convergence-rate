#!/usr/bin/env bash
# Claim 1: increasing precision switches the binding convergence budget.
#
# Test parameters:
#   lambda^2=13, N=80, P={30,45,90,180}, seeded zero window 1..5.
#
# Expected result:
#   Matching digits rise from approximately 49.238 to the fixed-cutoff prime
#   ceiling approximately 55.654, then remain at that ceiling as P increases.
set -euo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$REPO_ROOT"

TARGET_DIR=${CARGO_TARGET_DIR:-"$REPO_ROOT/target"}
BIN=${BIN:-"$TARGET_DIR/release/ccm-convergence-rate"}
if [[ ! -x "$BIN" ]]; then
  cargo build --quiet --release --features hp --locked \
    --bin ccm-convergence-rate --target-dir "$TARGET_DIR"
fi

python3 scripts/reproduce.py budget-switch \
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
