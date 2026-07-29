#!/usr/bin/env bash
# Claim 13: smooth prime ceiling.
# Full grid: lambda^2=4..30, N=300, P=200; --quick truncates at 15.
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/claim_common.sh"
run_convergence_claim prime-smooth "$@"
