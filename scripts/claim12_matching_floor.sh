#!/usr/bin/env bash
# Claim 12: matching and eigenvalue floors remain distinct at lambda^2=200.
#
# Test parameters:
#   lambda^2=200, N={2400,2800}, P=1250, seeded zero window 1..5.
#
# Expected result:
#   Matching digits saturate near 1070.4 and agree with the matching-floor
#   formula (approximately 1070.5) within 3 digits.
set -euo pipefail

source "$(dirname -- "${BASH_SOURCE[0]}")/claim_common.sh"
claim_run matching-floor "$@"
