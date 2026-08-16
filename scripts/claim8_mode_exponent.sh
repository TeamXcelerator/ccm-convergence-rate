#!/usr/bin/env bash
# Claim 8: the fitted mode exponent follows q(lambda^2).
#
# Model:
#   q(lambda^2) = 2/(2*gamma + log(log(lambda^2)))
#   equivalently, 1/q = c0 + c1*log(log(lambda^2)).
#
# Shared test grid (eight N values per cutoff):
#   lambda^2=7,   N={3,5,7,9,11,13,15,18},              P=200
#   lambda^2=13,  N={7,11,16,21,27,33,39,44},           P=200
#   lambda^2=20,  N={12,20,28,38,48,58,68,78},          P=300
#   lambda^2=25,  N={16,28,40,55,70,85,98,108},         P=300
#   lambda^2=50,  N={40,70,105,140,175,210,240,260},    P=500
#   lambda^2=100, N={90,170,250,330,410,490,560,620},   P=700
#
# Expected result:
#   The fitted q values track the paper's Table 1. The unconstrained regression
#   over the reproduced cutoffs recovers values near the paper's reported
#   regression. The paper's lambda^2=150 and 200 rows remain reference values
#   until their exact source configurations are established.
#
# This claim uses zero 1 and the same measurements as Claim 4. Reuse the same
# RESULTS_DIR and add --resume to avoid repeating the numerical sweep.
set -euo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$REPO_ROOT"

TARGET_DIR=${CARGO_TARGET_DIR:-"$REPO_ROOT/target"}
BIN=${BIN:-"$TARGET_DIR/release/ccm-convergence-rate"}
if [[ ! -x "$BIN" ]]; then
  cargo build --quiet --release --features hp --locked \
    --bin ccm-convergence-rate --target-dir "$TARGET_DIR"
fi

python3 scripts/reproduce.py mode-exponent \
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
