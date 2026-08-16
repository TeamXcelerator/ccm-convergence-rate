#!/usr/bin/env bash
# Claim 7: the small-N archimedean convergence rate has a parameter-free slope.
#
# Test parameters:
#   lambda^2=7, N={2,3,4,5,6,7,8}, P=200, seeded zero 1.
#
# Expected result:
#   The predicted slope is pi^2/(ln(10)*ln(7))=2.203 digits per mode. The paper
#   reports approximately 2.264; the check allows 15% relative deviation.
#   Larger zero windows are not resolved at N=2.
set -euo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$REPO_ROOT"

TARGET_DIR=${CARGO_TARGET_DIR:-"$REPO_ROOT/target"}
BIN=${BIN:-"$TARGET_DIR/release/ccm-convergence-rate"}
if [[ ! -x "$BIN" ]]; then
  cargo build --quiet --release --features hp --locked \
    --bin ccm-convergence-rate --target-dir "$TARGET_DIR"
fi

python3 scripts/reproduce.py archimedean-slope \
  --bin "$BIN" \
  --root-acquisition "${ROOT_ACQUISITION_MODE:-seeded}" \
  --parity-policy "${PARITY_POLICY:-even-sector}" \
  --eigenstate-solver "${EIGENSTATE_SOLVER:-auto}" \
  --research-capture "${RESEARCH_CAPTURE_LEVEL:-research}" \
  --research-sector-eigenpairs "${RESEARCH_SECTOR_EIGENPAIRS:-8}" \
  --first-zero-index 1 \
  --zero-count 1 \
  --analysis-zero-index 1 \
  --results-dir "${RESULTS_DIR:-"$REPO_ROOT/outputs"}" \
  "$@"
