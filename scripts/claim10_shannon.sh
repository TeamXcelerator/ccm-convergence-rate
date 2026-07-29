#!/usr/bin/env bash
# Claim 10: Shannon-coordinate saturation.
# Grid: lambda^2=100, N=100..1200 by 100, P=700.
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/claim_common.sh"
run_convergence_claim shannon "$@"
