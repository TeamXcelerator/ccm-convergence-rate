#!/usr/bin/env bash
# Claim 14: fixed-cutoff prime bottleneck.
# Grid at lambda^2=13: (N,P)={(40,100),(80,200),(120,400),(200,800)}.
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/claim_common.sh"
run_convergence_claim bottleneck "$@"
