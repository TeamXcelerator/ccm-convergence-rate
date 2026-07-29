#!/usr/bin/env bash
# Claim 7: archimedean initial slope at lambda^2=7.
# Grid: N=2..8, P=200.
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/claim_common.sh"
run_convergence_claim archimedean-slope "$@"
