#!/usr/bin/env bash
# Claim 13: the finite-cutoff prime ceiling rises smoothly rather than as a
# prime-power staircase.
#
# Test parameters:
#   lambda^2={4,5,...,30}, N=300, P=200, seeded zero window 1..5.
#   --quick truncates the cutoff sweep at lambda^2=15.
#
# Expected result:
#   The mean rise is approximately 5.3 matching digits per unit lambda^2.
#   The check accepts a mean between 4.5 and 6.0 and reports prime-power and
#   ordinary-step statistics separately.
set -euo pipefail

source "$(dirname -- "${BASH_SOURCE[0]}")/claim_common.sh"
claim_run prime-smooth "$@"
