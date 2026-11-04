#!/usr/bin/env bash
# Claim 2: the working-precision budget has unit leading slope.
#
# Test parameters:
#   lambda^2=50, N=400, P={50,100,150,200}, seeded zero window 1..5.
#
# Expected result:
#   The fit has |dD/dP - 1| <= 0.005 and R^2 >= 0.999. The current paper
#   reports slope 1.00205 and R^2=0.99994.
set -euo pipefail

source "$(dirname -- "${BASH_SOURCE[0]}")/claim_common.sh"
claim_run precision-slope "$@"
