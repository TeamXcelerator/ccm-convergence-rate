#!/usr/bin/env bash
# Claim 10: practical mode saturation occurs at a fixed Shannon coordinate.
#
# Test parameters:
#   lambda^2=100, N={100,200,...,1200}, P=700, seeded zero window 1..5.
#
# Expected result:
#   The first point with g=D/D_Primes >= 0.98 has
#   N/(lambda^2*ln(lambda^2)) approximately 2.0--2.3; the check accepts
#   the wider validation band 1.8--2.6.
set -euo pipefail

source "$(dirname -- "${BASH_SOURCE[0]}")/claim_common.sh"
claim_run shannon "$@"
