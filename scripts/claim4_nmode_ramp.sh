#!/usr/bin/env bash
# Claim 4: the normalized mode budget follows a tanh transition.
#
# Model:
#   g(N) = D(N)/D_Primes
#        = tanh((c*N/(lambda^2*log(lambda^2)))^q)
#
# Test grid (eight N values per cutoff):
#   lambda^2=7,   N={3,5,7,9,11,13,15,18},              P=200
#   lambda^2=13,  N={7,11,16,21,27,33,39,44},           P=200
#   lambda^2=20,  N={12,20,28,38,48,58,68,78},          P=300
#   lambda^2=25,  N={16,28,40,55,70,85,98,108},         P=300
#   lambda^2=50,  N={40,70,105,140,175,210,240,260},    P=500
#   lambda^2=100, N={90,170,250,330,410,490,560,620},   P=700
#
# Expected result:
#   Every normalized transition has low residual under the tanh model; the
#   claim check requires a maximum normalized RMSE no greater than 0.05.
#
# This published fit uses zero 1 only. A multi-root window is not defined at
# the smallest N values. Add --quick to retain only lambda^2 <= 25.
set -euo pipefail

source "$(dirname -- "${BASH_SOURCE[0]}")/claim_common.sh"
claim_run nmode-ramp "$@"
