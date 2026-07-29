#!/usr/bin/env bash
# Claims 4, 8, and 9: tanh mode ramp, q(lambda^2), and onset c.
# Full cutoffs: lambda^2={7,13,20,25,50,100,150,200}; eight N values each.
# Add --quick to retain only lambda^2 <= 25.
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/claim_common.sh"
run_convergence_claim nmode-ramp "$@"
