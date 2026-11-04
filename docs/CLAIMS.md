# Claim catalog

The numbered experiments reproduce the original scalar convergence study.
There are **14 numbered claims and 12 executable wrappers**. C5 and C6 are
analytic implications, with no numerical wrapper. The later indexed-root
sections of the working manuscript contain additional research results; the
12 wrappers are not a reproduction of every table and certificate in those
sections.

Throughout, `C = λ²`, `N` is the mode cutoff, `P` is requested decimal
precision, and `D` is relative matching digits for the selected root. The
published scalar fits concern zero 1. Changing the analyzed ordinal is an
exploratory comparison, not reproduction of that scalar table.

The [script catalog](../scripts/README.md) and each script's `--plan` output
give the exact current experiment grid. The [results guide](RESULTS.md)
distinguishes historical measurements from current Toolkit validation.

| Claim | Subject and numerical script | Scope of the claim |
|---|---|---|
| C1 | Error-budget demonstration; [claim1_budget_switch.sh](../scripts/claim1_budget_switch.sh) | The one-sided minimum bound is a triangle inequality. The sweep illustrates changing precision; it does not prove noncancellation or determine each component error. |
| C2 | Precision slope; [claim2_precision_slope.sh](../scripts/claim2_precision_slope.sh) | Tests slope 1 at fixed `C=50,N=400`. The analytic `P+O(1)` statement assumes appropriate stability and conditioning. |
| C3 | Precision-floor effects; [claim3_floor_artifact.sh](../scripts/claim3_floor_artifact.sh) | Records natural/even-state eigenvalues, signs, and reflection deviation. Finite observations do not establish continuum positivity or parity. |
| C4 | Saturating transition fit; [claim4_nmode_ramp.sh](../scripts/claim4_nmode_ramp.sh) | Fits the total intrinsic edge, combining mode and cutoff effects. The fit is distinct from the pure truncation-error channel. |
| C5 | Stretched-exponential coordinate identity | If `D_mode=(a/ln 10)N^q+o(N^q)`, then the error is `exp(-aN^q+o(N^q))`. This is a conditional change of coordinates, not a regularity theorem. |
| C6 | Conditional local exponent | The logarithmic derivative conclusion needs the stated derivative control on the remainder. Transferring eigenvalue rates to root rates needs separate spectral and root hypotheses. |
| C7 | Small-cutoff mode slope; [claim7_archimedean_slope.sh](../scripts/claim7_archimedean_slope.sh) | Compares a finite `C=7` slope with the candidate archimedean rate. The Gamma-factor envelope alone does not prove the CCM mode rate. |
| C8 | Mode-exponent fit; [claim8_mode_exponent.sh](../scripts/claim8_mode_exponent.sh) | Tests the calibrated finite-window formula on the declared grid. Its unchanged extrapolation to larger cutoffs is not a uniform law. |
| C9 | Onset coefficient; [claim9_onset_constant.sh](../scripts/claim9_onset_constant.sh) | Tests the fitted coefficient near `4/π`. This empirical argument coefficient is not the linear crossover multiplier in C10. |
| C10 | Shannon-like crossover; [claim10_shannon.sh](../scripts/claim10_shannon.sh) | The candidate ceiling and linear slope imply `N_linear=(4/π)C log C`. Their transfer to the CCM error and identification with a specific time–band limiting operator remain open. |
| C11 | Cutoff-floor anchor; [claim11_prime_anchor.sh](../scripts/claim11_prime_anchor.sh) | Checks the historical finite `C=100` measurement. The prolate asymptotic is distinct from the unproved full CCM cutoff transfer. |
| C12 | Matching-floor comparison; [claim12_matching_floor.sh](../scripts/claim12_matching_floor.sh) | Compares two finite `C=200` saturation points with the empirical matching-floor formula; it does not certify a limiting floor. |
| C13 | Unit-cutoff increments; [claim13_prime_smooth.sh](../scripts/claim13_prime_smooth.sh) | Summarizes the finite digit increments and prime-power groups. A finite average cannot establish statistical indistinguishability or a universal smooth rate. |
| C14 | Fixed-cutoff plateau; [claim14_bottleneck.sh](../scripts/claim14_bottleneck.sh) | Tests a finite plateau at `C=13`. The manuscript's fixed-cutoff limit is conditional on the selected continuum branch and noncoincidence hypotheses. |

## Precision-floor controls

C1, C2, and C3 deliberately include working precisions at which the lowest
stored eigenvalues may be unresolved or the selected state may not be the
algebraic ground state. These controls explicitly use the Toolkit's
`RecordOutcome` policy. The directed ground-index proof still runs; its outcome
and reason remain in the source-bound result. This policy has a distinct
artifact identity. The other numerical claims require the ground-index proof.

An unsuccessful proof does not turn a selected stored state into a ground
state. Its root measurements describe that selected state, and claims requiring
a proven ground state remain `UNASSESSED`. A finite precision-slope check can
still assess the measured response to precision within that narrower scope.
C1 and C3 are descriptive controls with no positive hypothesis verdict.

The published `C,N,P` grids remain fixed. Increasing a low-precision row's source
precision until it looks well resolved would change the experiment. Likewise,
blocked ground-dependent diagnostics remain blocked; recording the precision
control does not establish complete Ultra coverage.

These three wrappers also request the explicit `paper3-precision-control-v3`
capture assessment. It distinguishes completeness of the applicable controls
from completeness of all requested Ultra diagnostics. The raw receipt remains
unchanged. Only recognized failures of the stored-precision separation premises,
bound to the actual source, build, and configuration, can be classified as
unavailable for that control. Missing inputs, resource failures, and unknown
errors still make the run incomplete. Acquired cluster assessments can retain
an unresolved outcome; they do not certify a cluster or invent its vectors.
The nonground and counted-cluster cases require the selected state's retained
bracket and a conservative widened bracket to lie below the storage policy
scale with a factor-of-two margin. A sign-unresolved interval does not turn a
conclusive nonground result into a ground-state proof.

The summary preserves `all_requested_capture_complete` and the separate
`applicable_capture_complete` value, together with each qualified diagnostic
and its original outcome. An applicable-control pass with raw Ultra coverage
incomplete must not be described as complete Ultra acquisition.

## Shared measurements

C4, C8, and C9 analyze the same ramp grid. Preserve the original result
directory and use the explicit resume mechanism to reuse authenticated
measurements. Do not copy older JSON into a new run or change the producing
Toolkit revision in a saved record. Incompatible records require fresh
calculation and retain their historical identity.

The executable ramp grid covers `C=7,13,20,25,50,100`. The historical table's
`C=150,200` fit rows lack the exact original ramp configurations; they are
reference-only rows. They must not appear as completed current reproductions.

`--quick` reduces the documented grid and skips the large saturation claims.
Completion of that subset does not establish completion of the full claim
catalog.

## Scope of the convergence criterion

For fixed cutoff, the manuscript assumes a simple isolated positive continuum
ground eigenvalue, an even normalized ground state, and a simple isolated
transform zero different from the first zeta zero. Under those assumptions,
the selected finite-section branch converges to a nonzero cutoff error when
numerical perturbations vanish.

That statement is a selected-branch limit. It is not an unconditional
supremum over all finite `N,P`, and it does not rule out every bounded family
of cutoffs without a uniform separation hypothesis. Along growing cutoffs,
vanishing separately defined mode, cutoff, and numerical errors is sufficient
for convergence. Necessity does not follow from a triangle inequality because
signed errors may cancel.

The detailed hypotheses and proofs remain in the manuscript's “Convergence
criterion” section and rigor ledger. Software completion cannot discharge
those analytic obligations.
