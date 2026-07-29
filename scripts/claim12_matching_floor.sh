#!/usr/bin/env bash
# Claim 12: matching/eigenvalue two-floor structure.
# Grid: lambda^2=200, N={2400,2800}, P=1250.
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/claim_common.sh"
run_convergence_claim matching-floor "$@"
