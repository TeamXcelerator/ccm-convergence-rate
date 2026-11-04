#!/usr/bin/env bash
# Claim 1: inspect the finite precision response at fixed cutoff and mode count.
#
# Test parameters:
#   lambda^2=13, N=80, P={30,45,90,180}, seeded zero window 1..5.
#
# Historical comparison (descriptive; no fixed acceptance gate):
#   Matching digits rise from approximately 49.238 to the fixed-cutoff prime
#   ceiling approximately 55.654, then remain at that ceiling as P increases.
set -euo pipefail

source "$(dirname -- "${BASH_SOURCE[0]}")/claim_common.sh"
claim_run budget-switch "$@"
