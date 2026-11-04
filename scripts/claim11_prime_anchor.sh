#!/usr/bin/env bash
# Claim 11: the saturated lambda^2=100 configuration anchors the prime ceiling.
#
# Test parameters:
#   lambda^2=100, N=1000, P=700, seeded zero window 1..5.
#
# Expected result:
#   D_Primes(100)=526.08 matching digits; the check accepts +/-3 digits.
set -euo pipefail

source "$(dirname -- "${BASH_SOURCE[0]}")/claim_common.sh"
claim_run prime-anchor "$@"
