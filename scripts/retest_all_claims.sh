#!/usr/bin/env bash
# Run every empirical claim in paper order. Pass --quick for the light tier.
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/claim_common.sh"
run_convergence_claim all "$@"
