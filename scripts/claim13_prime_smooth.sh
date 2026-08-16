#!/usr/bin/env bash
# Claim 13: the finite-cutoff prime ceiling rises smoothly rather than as a
# prime-power staircase.
#
# Test parameters:
#   lambda^2={4,5,...,30}, N=300, P=200, seeded zero window 1..5.
#   --quick truncates the cutoff sweep at lambda^2=15.
#
# Expected result:
#   The mean rise is approximately 5.3 matching digits per unit lambda^2.
#   The check accepts a mean between 4.5 and 6.0 and reports prime-power and
#   ordinary-step statistics separately.
set -euo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$REPO_ROOT"

TARGET_DIR=${CARGO_TARGET_DIR:-"$REPO_ROOT/target"}
BIN=${BIN:-"$TARGET_DIR/release/ccm-convergence-rate"}
if [[ ! -x "$BIN" ]]; then
  cargo build --quiet --release --features hp --locked \
    --bin ccm-convergence-rate --target-dir "$TARGET_DIR"
fi

python3 scripts/reproduce.py prime-smooth \
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
