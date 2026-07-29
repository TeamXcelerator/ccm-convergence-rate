#!/usr/bin/env bash
# Shared Paper 3 claim launcher. Claim scripts remain intentionally small and
# readable; the Python backend performs only structured collection and fits.
set -euo pipefail

CLAIM_REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$CLAIM_REPO_ROOT"

RESEARCH_CAPTURE_LEVEL=${RESEARCH_CAPTURE_LEVEL:-research}
RESEARCH_SECTOR_EIGENPAIRS=${RESEARCH_SECTOR_EIGENPAIRS:-8}
ROOT_ACQUISITION_MODE=${ROOT_ACQUISITION_MODE:-seeded}
PARITY_POLICY=${PARITY_POLICY:-even-sector}
EIGENSTATE_SOLVER=${EIGENSTATE_SOLVER:-auto}
FIRST_ZERO_INDEX=${FIRST_ZERO_INDEX:-1}
ZERO_COUNT=${ZERO_COUNT:-5}
ANALYSIS_ZERO_INDEX=${ANALYSIS_ZERO_INDEX:-1}
RESULTS_DIR=${RESULTS_DIR:-"$CLAIM_REPO_ROOT/outputs"}

if [[ -z "${BIN+x}" ]]; then
  CLAIM_TARGET_DIR=${CARGO_TARGET_DIR:-"$CLAIM_REPO_ROOT/target"}
  cargo build --quiet --release --features hp --locked \
    --bin ccm-convergence-rate \
    --target-dir "$CLAIM_TARGET_DIR"
  BIN="$CLAIM_TARGET_DIR/release/ccm-convergence-rate"
elif [[ ! -x "$BIN" ]]; then
  echo "Configured convergence binary is not executable: $BIN" >&2
  exit 1
fi

run_convergence_claim() {
  local claim=$1
  shift
  python3 "$CLAIM_REPO_ROOT/scripts/reproduce.py" "$claim" \
    --bin "$BIN" \
    --root-acquisition "$ROOT_ACQUISITION_MODE" \
    --parity-policy "$PARITY_POLICY" \
    --eigenstate-solver "$EIGENSTATE_SOLVER" \
    --research-capture "$RESEARCH_CAPTURE_LEVEL" \
    --research-sector-eigenpairs "$RESEARCH_SECTOR_EIGENPAIRS" \
    --first-zero-index "$FIRST_ZERO_INDEX" \
    --zero-count "$ZERO_COUNT" \
    --analysis-zero-index "$ANALYSIS_ZERO_INDEX" \
    --results-dir "$RESULTS_DIR" \
    "$@"
}
