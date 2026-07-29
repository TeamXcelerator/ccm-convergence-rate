#!/usr/bin/env bash
# Claim 3: precision-floor, sign, and natural-evenness evidence.
# Grid: lambda^2=50, N=400, P={50,150,300}.
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/claim_common.sh"
run_convergence_claim floor-artifact "$@"
