# A Quantitative Convergence Law for the CCM Zeta Spectral Triple

Companion repository for the paper

> **A Quantitative Convergence Law for the Connes–Consani–Moscovici Zeta
> Spectral Triple**
> Ronnie Andrews, Jr. (Team Xcelerator Inc.®), 2026.
> Zenodo: [doi:10.5281/zenodo.20938200](https://doi.org/10.5281/zenodo.20938200)

**Author:** Ronnie Andrews, Jr.  
**ORCID:** [0009-0003-9724-3104](https://orcid.org/0009-0003-9724-3104)  
**Contact:** randrewsmath@gmail.com  
**Release:** v1.2 (August 2026)
**Toolkit:** Xcelerator Toolkit v0.13.5

> **New in v1.2.** This release adds the exact finite-band reach
> `T_max = 2πN/ln(λ²)`, its Riemann–von Mangoldt zero-capacity estimate,
> configurable multi-zero measurement windows, independently runnable claim
> scripts, and Toolkit v0.13.5 integration. Historical v1.1 manuscript files
> remain frozen snapshots.

> **New in v1.1.** The convergence law is now stated in two equivalent forms: an
> *intrinsic* two-channel spectral error (modes and primes), which carries the
> mathematics, and its *finite-precision measurement* in matching digits. The
> working-precision term is a measurement cap, not a third mathematical budget.

---

## What this paper does

The Connes–Consani–Moscovici (CCM) construction (arXiv:2511.22755) and its
Connes–van Suijlekom refinement (arXiv:2511.23257) produce finite real
symmetric matrices whose ground state yields an approximation `ν₁` to the
first nontrivial Riemann zero `γ₁`. The accuracy sharpens as three parameters
grow: a prime cutoff `λ²`, a basis size `N`, and the working precision `P`. The
rate of convergence in `N` is named the central open problem in arXiv:2511.22755.

The paper characterizes that convergence and states it — the **Andrews CCM
Convergence Law** — in two equivalent forms.

**Intrinsic (spectral) form.** The construction's relative error is a single
two-channel quantity,

```
E(N, λ²) = ε_modes(N, λ²) + ε_primes(λ²)
```

a mode channel `ε_modes ~ exp(−a·N^q)` that vanishes as `N → ∞`, and a prime
channel `ε_primes` that vanishes as `λ² → ∞`. Convergence `ν₁ → γ₁` is exactly
`E → 0`, and requires both limits. The two channels are the finite-`N` transition
and the extreme tail of a single prolate-type spectral edge. This form makes no
reference to precision — it is the mathematics of the construction.

**Observed (digit) form.** With the matching-digit count
`D = −log₁₀(|ν₁−γ₁|/|γ₁|)`, so that `D → ∞` is exactly `ν₁ → γ₁`, a computation at
working precision `P` resolves the intrinsic error only down to its round-off
floor:

```
D(λ², N, P) = min( D_Wprec(P),  D_nModes(N, λ²),  D_Primes(λ²) )
```

the minimum of three budgets — precision, modes, prime content — of which
precision is the instrument resolution, absent from the intrinsic form. In digit
space the minimum is **forced, not fitted** (`D` is a negative logarithm of a sum
of independent errors, so the largest binds), which is why earlier
single-expression digit fits fail.

This repository contains the paper, its source, and a one-command driver that
reproduces each empirical claim. The reproduction driver retains a configurable
window of zero ordinals in every measurement. The published scalar fits remain
zero-1 baselines; selecting a higher ordinal supports the ongoing extension of
the convergence law without discarding the other roots.

The current manuscript also separates convergence quality from finite spectral
reach. The retained basis has exact outer frequency
`T_max = 2πN/ln(λ²)`. Substitution into the Riemann–von Mangoldt law gives a
geometric zero-capacity estimate
`K_max^(0) = (N/ln(λ²))[ln(N/ln(λ²)) − 1] + 7/8`. These quantities describe
which ordinates fit inside the finite band; they do not guarantee accurate or
correctly ordered recovery.

> This README is a guide to the claims and how to reproduce them. It is **not**
> a substitute for the paper, which carries the derivations, proofs, and the
> precise rigor ledger (§9, Table 2).

## Headline numbers

| Quantity | Value | Configuration |
|---|---|---|
| Precision slope `∂D/∂P` | `1.00205` (`R²=0.99994`; predicted `1`) | λ²=50, N=400, P swept |
| Prime ceiling `D_Primes(100)` | `526.08` digits | λ²=100, N=1000, HP-700 |
| Prime ceiling `D_Primes(200)` | `≈ 1070.4` digits | λ²=200, N≥2400, HP-1250 |
| Leading coefficient `K` | `4π/ln10 = 5.45750…` (exact) | prolate asymptotic |
| Archimedean slope (λ²=7) | predicted `2.203`, measured `2.264` (≈3%) | small-N regime |
| Mode exponent `q(λ²)` | `2/(2γ + ln ln λ²)`, crosses 1 near λ²≈13 | per-λ² ramp fits |
| Onset constant `c` | `≈ 4/π = 1.273` | per-λ² ramp fits |
| Finite-band edge `T_max` | `2πN/ln(λ²)` | exact basis identity |
| Geometric zero capacity `K_max^(0)` | `(N/ln(λ²))[ln(N/ln(λ²))−1] + 7/8` | Riemann–von Mangoldt estimate at `T_max` |

---

## Claims and how they are backed

Claims are listed in the order they appear in the paper. Each is tagged with its
**rigor tier** (T1 rigorous; T2 derived modulo one named lemma; T3 derived in
structure and validated against data; T4 empirical — see Table 2 of the paper).
Empirical claims have a one-line reproduction command; derived claims show the
core result and point to the relevant section.

### C1 — The minimum is forced (§3, Prop. 1) · **T1** · *derived*

Because `D` is a negative logarithm of a sum of independent positive errors, the
largest error dominates and `D = min(D_Wprec, D_nModes, D_Primes) + O(1)`
(`max ≤ Σ ≤ 3·max`, and `log₁₀3 < 0.48`). The `min` agrees with `D` to within half a digit; what a single smooth term
cannot capture is the combination of a hard precision wall, a prime ceiling, and
a `λ²`-coupled mode ramp (the precision junction is sharp; the mode→prime
junction is a smooth `tanh` saturation). The precision budget is a measurement
cap, not mathematics; removing it leaves the single intrinsic two-channel edge
(the intrinsic form above). *Full statement: §3.*

Low-scale demonstration of the budget switching:
```bash
bash scripts/claim1_budget_switch.sh
```

### C2 — Precision budget `D_Wprec = P + O(1)`, slope exactly 1 (§4) · **T1** · *empirical*

Finite precision `P` introduces relative round-off `~10⁻ᴾ`, amplified by a
`P`-independent condition number, so `D_Wprec(P) = P − log₁₀κ = P + O(1)` with
leading coefficient exactly 1.
```bash
bash scripts/claim2_precision_slope.sh
```
Expected: `|∂D/∂P − 1| ≤ 0.005`. The current reproduction gives
`1.00205` with `R²=0.99994`.

### C3 — Symmetry, positivity, and the precision floor (§4.1) · **T4** · *empirical*

Above the precision floor the smallest eigenvalue is even and positive — a
genuine feature of the operator, not of the regime. Below the floor, results are
precision-starved (spurious symmetry/sign); raising `P` past the floor dissolves
the artifacts.
```bash
bash scripts/claim3_floor_artifact.sh
```
The full even-symmetry reproduction (38 configurations, natural vs forced-even
eigenvector, numerically equivalent above floor) is documented in the independent
reproduction (doi:10.5281/zenodo.20427499):
[ccm-reproduction-and-convergence](https://github.com/TeamXcelerator/ccm-reproduction-and-convergence).
The command above now also records the natural and forced-even eigenvalues,
their signs, and the reflection deviation at every tested precision.

### C4 — Mode budget is a `tanh` ramp (§5) · **T3** · *empirical*

```
D_nModes(N, λ²) = D_Primes(λ²) · tanh( (c·N/(λ²·ln λ²))^q ),   q = 2/(2γ + ln ln λ²)
```
Claim 4 reports the normalized ramp fit and its residual separately:
```bash
bash scripts/claim4_nmode_ramp.sh                 # add --quick for λ²≤25 only
```
Expected: each cutoff follows the normalized `tanh` transition with maximum
normalized RMSE no greater than `0.05`.

### C5 — Stretched-exponential identity (§5.1, Thm. 1(i)) · **T1** · *derived*

If the pre-saturation ramp is `D_nModes = (a/ln10)·Nq (1+o(1))`, then the
relative error is `exp(−a·Nq)(1+o(1))` — immediate from `err = 10⁻ᴰ`. Hence `q`
is not a fitting knob but the **analyticity class** of the eigenvector (`q=1`
strip-analytic; `0<q<1` sub-exponential; `q→0` finite Sobolev). *Proof: §5.1.*
Illustrated by the C4 ramp data on a log-log scale.

### C6 — Reconciliation with the eigenvalue-space rate (§5.1, Thm. 1(ii)) · **T1** · *derived*

A power-law fit `err ~ C·N^{−2s}` over a window about `N` returns the **local**
exponent `2s_loc(N) = a·q·Nq`. So the Galerkin exponent measured by Groskin
(arXiv:2605.20224) is the local slope of this stretched-exponential, not a fixed
Sobolev index; it must grow with `N`. The factor 2 is the self-adjoint identity
`|ε−ε_N| = O(‖ξ−ξ_N‖²)`. *Proof: §5.1.*

### C7 — Archimedean leading rate `δ = π/4` (§5.2) · **T3** · *derived + validated*

The analyticity strip of the limiting Fourier–Mellin function is set by the
archimedean `Γ_ℝ` factor;
`|Γ(¼+iz/2)| ~ exp(−π|z|/4)` by Stirling gives `δ = π/4`, hence the
parameter-free leading digit slope `∂D/∂N = π²/(ln10·ln λ²)`.
```bash
bash scripts/claim7_archimedean_slope.sh
```
Expected (λ²=7): predicted `2.203`, measured `≈ 2.264` (agreement ≈3%, no free
parameters).

### C8 — Mode exponent `q(λ²) = 2/(2γ + ln ln λ²)` (§5.3) · **T3** · *derived + validated*

The finite Euler product roughens the eigenvector; modeling the reciprocal
exponent as `1/q = c₀ + c₁·ln ln λ²` with `c₀ = γ` (archimedean baseline) and
`c₁ = ½` (Mertens variance prefactor) gives the closed form. A regression that
does **not** assume `γ` recovers it as the intercept.
```bash
bash scripts/claim8_mode_exponent.sh
```
Expected: per-λ² `q` tracking Table 1, and `c₀ ≈ γ = 0.577`, `c₁ ≈ ½`,
`R² ≈ 0.98`.

### C9 — Onset constant `c ≈ 4/π` (§5.3) · **T3** · *empirical*

Across the per-λ² fits the onset constant clusters near `4/π = 1.273`.
```bash
bash scripts/claim9_onset_constant.sh
```
Expected: the mean fitted onset constant lies within `0.1` of `4/π`.

Claims 4, 8, and 9 intentionally use the same numerical grid. Run Claim 4
first, retain its `RESULTS_DIR`, and pass `--resume` to Claims 8 and 9 to reuse
the structured measurements without repeating the expensive sweep.

### C10 — Shannon coordinate `λ²·ln λ²` (§5.4, Lem. 2) · **T2** · *derived + validated*

The ramp meets its ceiling at `N* = D_Primes / (∂D/∂N) = (4/π)·λ²·ln λ²` — the
time–frequency Shannon number of the box (Landau–Pollak; Slepian–Pollak;
Landau–Widom). The coordinate is forced, not posited.
```bash
bash scripts/claim10_shannon.sh               # server-grade (λ²=100 to saturation)
```
Expected: saturation at `N/(λ²·ln λ²) ≈ 2.0–2.3`.

### C11 — Prime ceiling leading coefficient `K = 4π/ln10` (§6) · **T2** · *derived + validated*

The eigenvalue floor `D_eig = −log₁₀ ε∞(λ)` ties to the principal prolate
spheroidal eigenvalue; the asymptotic gives `D_eig = Kλ² − (9/2ln10)·ln λ² − C₀`,
with `K = 4π/ln10` exact and parameter-free, `9/2` the Fuchs index, and
`C₀ = log₁₀(2¹⁴√2·π⁵/3) = 6.3736…`. The matching floor the law consumes sits a
few digits below (C12).
```bash
bash scripts/claim11_prime_anchor.sh          # server-grade (~20-40 min)
```
Expected: `D_Primes(100) = 526.08`.

### C12 — Matching floor / two-floor structure (§6) · **T4** · *empirical*

The matching floor the minimum actually consumes, `D_Primes = Kλ² −
P_m·log₁₀λ² − c_m` with `P_m ≈ 5`, `c_m ≈ 9.5`, sits a few digits below the
eigenvalue floor `D_eig`; the difference is the *conversion gap*
`conv = D_eig − D_Primes`. At λ²=200 the saturated measurement sits at the
matching floor, confirming the two-floor structure at the largest cutoff measured.
```bash
bash scripts/claim12_matching_floor.sh        # server-grade (multi-hour, HP-1250)
```
Expected: `D_Primes(200) ≈ 1070.4`; matching floor `1070.5`; eigenvalue floor
`1074.77`; gap ≈ 4.3.

### C13 — The floor is smooth, not a prime staircase (§6) · **T2** · *empirical*

Sweeping `λ²` in unit steps (`N`, `P` above floor) gives a smooth rise of
`≈ 5.3` digits per unit `λ²`; prime-power entries are statistically
indistinguishable from non-prime entries.
```bash
bash scripts/claim13_prime_smooth.sh          # add --quick for λ²∈[4,15]
```

### C14 — Convergence criterion and the prime bottleneck (§7, Prop. 2) · **T1** · *derived*

For every fixed `λ²`, `sup_{N,P} D = D_Primes(λ²) < ∞`: no basis size or
precision reaches the zero, so convergence to `γ₁` forces `λ² → ∞`. And
`ν₁ → γ₁` iff all three budgets diverge. *Proof: §7.* Demonstration:
```bash
bash scripts/claim14_bottleneck.sh
```
Expected: at fixed λ²=13, `D` plateaus at the ceiling regardless of `N`, `P`.

---

## Reproduction

### Requirements

- **Rust** (stable) with the Xcelerator Toolkit dependencies — pulled
  automatically by Cargo (pinned to a tagged release). No manual cloning of the
  toolkit is required.
- **GMP / MPFR / MPC** for the high-precision (`hp`) build.
- **Python 3.8+** for the driver — **standard library only**, no `pip` install.

On **Windows**, the `hp` build must be done inside **WSL2** (the MSVC target is
not supported by the GMP/MPFR bindings). On Linux/WSL:

```bash
sudo apt install build-essential m4 libgmp-dev libmpfr-dev libmpc-dev
cargo build --release --features hp --locked
```

### Running

```bash
# one claim
bash scripts/claim2_precision_slope.sh

# everything, light configs only (minutes on a laptop / WSL2)
bash scripts/retest_all_claims.sh --quick

# everything, including server-grade claims (hours, large memory)
bash scripts/retest_all_claims.sh
```

Each command streams the complete toolkit output, stores a log and structured
JSON for every numerical point under `outputs/`, and prints a compact
**measured vs expected** verdict.

Most claims retain ordinals 1 through 5 while zero 1 supplies the paper's
scalar fit. The small-`N` Claim 4/8/9 ramp and Claim 7 initial-slope sweep
request only zero 1 because their first configurations cannot resolve a
distinct multi-root window. To study convergence beyond the first zero, use a
claim whose `N` range supports the requested window and select one ordinal
for the scalar fit:

```bash
bash scripts/claim2_precision_slope.sh \
  --first-zero-index 21 \
  --zero-count 10 \
  --analysis-zero-index 25 \
  --resume
```

All ten roots—including status, value, absolute and relative error, matching
digits, iteration count, correction, and residual—are retained in each JSON
measurement. A higher-ordinal verdict is labeled `EXPLORATORY`, because the
values printed in the current paper were fitted to zero 1.

Every claim exposes the numerical policies independently. The modern defaults
are reference-seeded acquisition, direct even-sector parity, the automatic
eigenstate solver, and balanced research capture:

```bash
bash scripts/claim2_precision_slope.sh \
  --root-acquisition independent \
  --parity-policy natural \
  --eigenstate-solver shift-invert-krylov \
  --research-capture maximum \
  --research-sector-eigenpairs 8
```

Supported parity policies are `natural`, `adaptive-even`, and `even-sector`.
Supported solvers are `legacy-inverse-iteration`, `shift-invert-krylov`, and
`auto`. Capture levels are `claim`, `research`, `gap`, and `maximum`.
These choices are independent and participate in structured-result and cache
identity; there is no bundled historical "paper profile."

In independent mode, this repository compares returned positive CCM roots with
reference zeros by ordinal position and records that comparison semantics.
Detailed displacement and signed-root classification are covered by the
companion independent-reproduction project linked below.

### Compute tiers

| Tier | Claims | Cost |
|---|---|---|
| **Light** (WSL2, minutes) | C1, C2, C3, C7, C13 (`--quick`), C14, and λ²≤25 of C4/C8/C9 | laptop-friendly |
| **Server** (hours, large memory) | C10 (Shannon), C11 (λ²=100 floor), C12 (λ²=200 floor), and λ²≥50 of C4/C8/C9 | excluded by `--quick` |

`--quick` runs only the light tier; server-grade claims print a clear banner and
are skipped.

### Notes

- The integrity-bound high-precision zero dataset is owned by the toolkit; this
  paper repository no longer carries a duplicate.
- An end-user run needs no cache environment setup. The toolkit defaults to
  local reuse plus public remote fetch. Current explicit modes are
  `XC_CACHE_MODE=reuse|refresh|require_reuse` and
  `XC_CACHE_REMOTE=none|public|private|private_public`.
- Author publication is controlled by the toolkit's normal author-profile and
  publication variables. During a sweep, computations stage artifacts with
  remote mutation suppressed; the driver performs one publication
  finalization after the entire claim succeeds.
- `--resume` accepts a prior JSON result only when its complete numerical
  identity matches the requested cutoff, mode count, precision, zero window,
  acquisition, parity policy, eigenstate solver, and capture level.
- `P` remains the requested decimal precision. Toolkit v0.13.5 derives its
  MPFR working precision from `P` and adds 64 guard bits; both values are
  reported, and the qualified working precision is part of artifact identity.
- Root records distinguish `converged`, `stagnated`, `approximate`, and
  `failed`. Stagnated values are retained with their achieved digits and
  diagnostics rather than silently promoted to converged results.
- The executable `q`/`c` reproduction grid currently stops at `λ²=100`.
  Table 1's `λ²=150` and `λ²=200` values remain manuscript reference values;
  their exact source configurations must be established before they are added
  to a full-grid reproduction.

---

## Repository layout

```
paper.tex / paper.pdf       the manuscript (current source + build)
paper_v1.1.tex / .pdf       frozen historical v1.1 snapshot
paper_v1.0.pdf              frozen snapshot matching the Zenodo v1.0 deposit
src/main.rs                 the `measure` binary (CCM construction + matching digits)
scripts/claim*.sh           readable, independently runnable claim definitions
scripts/reproduce.py        sweep, structured-result, and fit analysis backend
tests/integration.rs        toolkit wiring and bundled-dataset checks
outputs/                    ignored live logs and structured results
```

## Related work

- **Independent reproduction and convergence analysis** —
  [ccm-reproduction-and-convergence](https://github.com/TeamXcelerator/ccm-reproduction-and-convergence)
  · [doi:10.5281/zenodo.20427499](https://doi.org/10.5281/zenodo.20427499)
- **Falsification of prior convergence-rate predictions** —
  [ccm-convergence-rate-falsifications](https://github.com/TeamXcelerator/ccm-convergence-rate-falsifications)
  · [doi:10.5281/zenodo.20427673](https://doi.org/10.5281/zenodo.20427673)
- **Xcelerator Toolkit** — shared high-precision library:
  [xcelerator-toolkit](https://github.com/TeamXcelerator/xcelerator-toolkit)

## Citation

```bibtex
@misc{AndrewsCCMConvergenceLaw2026,
  author = {Andrews, Ronnie, Jr.},
  title  = {A Quantitative Convergence Law for the Connes--Consani--Moscovici
            Zeta Spectral Triple},
  year   = {2026},
  doi    = {10.5281/zenodo.20938200},
  note   = {Zenodo}
}
```

## License

See [LICENSE](LICENSE). Source-available for verification and study.
Not licensed for modification, redistribution, or commercial use.

## Trademarks

"Team Xcelerator Inc." is a registered trademark of Team Xcelerator Inc.
All other trademarks are the property of their respective owners.
