#!/usr/bin/env bash
# Claim 2: precision-budget slope.
# Grid: lambda^2=50, N=400, P={50,100,150,200}.
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/claim_common.sh"
run_convergence_claim precision-slope "$@"
