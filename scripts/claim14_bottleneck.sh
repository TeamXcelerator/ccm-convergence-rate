#!/usr/bin/env bash
# Claim 14: compare a finite N/P sweep with the fixed-cutoff plateau model.
#
# Test parameters:
#   lambda^2=13, (N,P)={(40,100),(80,200),(120,400),(200,800)},
#   seeded zero window 1..5.
#
# Expected result:
#   Matching digits saturate at the fixed-cutoff prime ceiling approximately
#   55.7; the final point must lie within 4 digits of that ceiling.
#   This finite check does not determine a supremum or a necessary condition
#   for convergence over arbitrarily large N and P.
set -euo pipefail

source "$(dirname -- "${BASH_SOURCE[0]}")/claim_common.sh"
claim_run bottleneck "$@"
