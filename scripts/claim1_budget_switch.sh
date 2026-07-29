#!/usr/bin/env bash
# Claim 1: force the binding budget to switch as precision rises.
# Grid: lambda^2=13, N=80, P={30,45,90,180}.
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/claim_common.sh"
run_convergence_claim budget-switch "$@"
