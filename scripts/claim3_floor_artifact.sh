#!/usr/bin/env bash
# Claim 3: record matching digits, sign, and symmetry across a precision sweep.
#
# Test parameters:
#   lambda^2=50, N=400, P={50,150,300}, seeded zero window 1..5.
#
# Historical comparison (descriptive; no fixed acceptance gate):
#   P=50 and 150 remain precision-limited and may have mixed natural symmetry
#   or differing signs. At P=300, matching digits reach the approximately
#   254.9-digit prime floor, natural/forced eigenvalues are numerically
#   equivalent and positive, and reflection deviation is negligible.
set -euo pipefail

source "$(dirname -- "${BASH_SOURCE[0]}")/claim_common.sh"
claim_run floor-artifact "$@"
