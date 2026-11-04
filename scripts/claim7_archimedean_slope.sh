#!/usr/bin/env bash
# Claim 7: the small-N archimedean convergence rate has a parameter-free slope.
#
# Test parameters:
#   lambda^2=7, N={2,3,4,5,6,7,8}, P=200, seeded zero 1.
#
# Expected result:
#   The predicted slope is pi^2/(ln(10)*ln(7))=2.203 digits per mode. The paper
#   reports approximately 2.264; the check allows 15% relative deviation.
#   Larger zero windows are not resolved at N=2.
set -euo pipefail

source "$(dirname -- "${BASH_SOURCE[0]}")/claim_common.sh"
claim_run archimedean-slope "$@"
