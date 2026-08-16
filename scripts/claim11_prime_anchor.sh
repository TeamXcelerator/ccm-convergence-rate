#!/usr/bin/env bash
# Claim 11: the saturated lambda^2=100 configuration anchors the prime ceiling.
#
# Test parameters:
#   lambda^2=100, N=1000, P=700, seeded zero window 1..5.
#
# Expected result:
#   D_Primes(100)=526.08 matching digits; the check accepts +/-3 digits.
set -euo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$REPO_ROOT"

TARGET_DIR=${CARGO_TARGET_DIR:-"$REPO_ROOT/target"}
BIN=${BIN:-"$TARGET_DIR/release/ccm-convergence-rate"}
if [[ ! -x "$BIN" ]]; then
  cargo build --quiet --release --features hp --locked \
    --bin ccm-convergence-rate --target-dir "$TARGET_DIR"
fi

python3 scripts/reproduce.py prime-anchor \
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
