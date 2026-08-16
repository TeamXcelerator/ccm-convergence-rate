#!/usr/bin/env bash
# Claim 9: the fitted mode-ramp onset constant clusters near 4/pi.
#
# Model:
#   g(N) = tanh((c*N/(lambda^2*log(lambda^2)))^q)
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
#   The per-cutoff onset constants cluster around 4/pi=1.273. The claim check
#   requires the mean fitted c to lie within 0.1 of 4/pi.
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

python3 scripts/reproduce.py onset-constant \
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
