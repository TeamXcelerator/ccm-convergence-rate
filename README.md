# A Quantitative Convergence Law for the CCM Zeta Spectral Triple

Companion repository for the paper

> **A Quantitative Convergence Law for the Connes–Consani–Moscovici Zeta
> Spectral Triple**
> Ronnie Andrews, Jr. (Team Xcelerator Inc.®), 2026.
> Zenodo: [doi:10.5281/zenodo.20938200](https://doi.org/10.5281/zenodo.20938200)

**Author:** Ronnie Andrews, Jr.  
**ORCID:** [0009-0003-9724-3104](https://orcid.org/0009-0003-9724-3104)  
**Contact:** randrewsmath@gmail.com  
**Date:** June 2026

---

## What this paper does

The Connes–Consani–Moscovici (CCM) construction (arXiv:2511.22755) and its
Connes–van Suijlekom refinement (arXiv:2511.23257) produce finite real
symmetric matrices whose ground state yields an approximation `ν₁` to the
first nontrivial Riemann zero `γ₁`. The accuracy sharpens as three parameters
grow: a prime cutoff `λ²`, a basis size `N`, and the working precision `P`. The
rate of convergence in `N` is named the central open problem in arXiv:2511.22755.

Writing the matching-digit count `D(λ²,N,P) = −log₁₀(|ν₁−γ₁|/|γ₁|)`, so that
`D → ∞` is exactly `ν₁ → γ₁`, the paper shows `D` obeys a single law — the
**Andrews CCM Convergence Law**:

```
D(λ², N, P) = min( D_Wprec(P),  D_nModes(N, λ²),  D_Primes(λ²) )
```

the minimum of three independent convergence budgets (precision, modes, prime
content). This repository contains the paper, its source, and a one-command
driver that reproduces each empirical claim.

> This README is a guide to the claims and how to reproduce them. It is **not**
> a substitute for the paper, which carries the derivations, proofs, and the
> precise rigor ledger (§9, Table 2).

## Headline numbers

| Quantity | Value | Configuration |
|---|---|---|
| Precision slope `∂D/∂P` | `1.000 ± 0.001` | λ²=100, N=1000, P swept |
| Prime ceiling `D_Primes(100)` | `526.08` digits | λ²=100, N=1000, HP-700 |
| Prime ceiling `D_Primes(200)` | `≈ 1070.4` digits | λ²=200, N≥2400, HP-1250 |
| Leading coefficient `K` | `4π/ln10 = 5.45750…` (exact) | prolate asymptotic |
| Archimedean slope (λ²=7) | predicted `2.203`, measured `2.264` (≈3%) | small-N regime |
| Mode exponent `q(λ²)` | `2/(2γ + ln ln λ²)`, crosses 1 near λ²≈13 | per-λ² ramp fits |
| Onset constant `c` | `≈ 4/π = 1.273` | per-λ² ramp fits |

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
junction is a smooth `tanh` saturation). *Full statement: §3.*

Low-scale demonstration of the budget switching:
```bash
python3 scripts/reproduce.py budget-switch
```

### C2 — Precision budget `D_Wprec = P + O(1)`, slope exactly 1 (§4) · **T1** · *empirical*

Finite precision `P` introduces relative round-off `~10⁻ᴾ`, amplified by a
`P`-independent condition number, so `D_Wprec(P) = P − log₁₀κ = P + O(1)` with
leading coefficient exactly 1.
```bash
python3 scripts/reproduce.py precision-slope
```
Expected: `∂D/∂P = 1.000 ± 0.001`.

### C3 — Symmetry, positivity, and the precision floor (§4.1) · *empirical*

Above the precision floor the smallest eigenvalue is even and positive — a
genuine feature of the operator, not of the regime. Below the floor, results are
precision-starved (spurious symmetry/sign); raising `P` past the floor dissolves
the artifacts.
```bash
python3 scripts/reproduce.py floor-artifact
```
The full even-symmetry reproduction (38 configurations, natural vs forced-even
eigenvector, bit-identical above floor) is documented in the independent
reproduction (doi:10.5281/zenodo.20427499):
[ccm-reproduction-and-convergence](https://github.com/TeamXcelerator/ccm-reproduction-and-convergence).

### C4 — Mode budget is a `tanh` ramp (§5) · **T3** · *empirical*

```
D_nModes(N, λ²) = D_Primes(λ²) · tanh( (c·N/(λ²·ln λ²))^q ),   q = 2/(2γ + ln ln λ²)
```
Reproduced together with C8 and C9 by the per-λ² ramp fits:
```bash
python3 scripts/reproduce.py nmode-ramp           # add --quick for λ²≤25 only
```

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
python3 scripts/reproduce.py archimedean-slope
```
Expected (λ²=7): predicted `2.203`, measured `≈ 2.264` (agreement ≈3%, no free
parameters).

### C8 — Mode exponent `q(λ²) = 2/(2γ + ln ln λ²)` (§5.3) · **T3** · *derived + validated*

The finite Euler product roughens the eigenvector; modeling the reciprocal
exponent as `1/q = c₀ + c₁·ln ln λ²` with `c₀ = γ` (archimedean baseline) and
`c₁ = ½` (Mertens variance prefactor) gives the closed form. A regression that
does **not** assume `γ` recovers it as the intercept.
```bash
python3 scripts/reproduce.py nmode-ramp
```
Expected: per-λ² `q` tracking Table 1, and `c₀ ≈ γ = 0.577`, `c₁ ≈ ½`,
`R² ≈ 0.98`.

### C9 — Onset constant `c ≈ 4/π` (§5.3) · **T3** · *empirical*

Across the per-λ² fits the onset constant clusters near `4/π = 1.273`. Produced
by the same `nmode-ramp` run as C8 (column `c meas`).

### C10 — Shannon coordinate `λ²·ln λ²` (§5.4, Lem. 2) · **T2** · *derived + validated*

The ramp meets its ceiling at `N* = D_Primes / (∂D/∂N) = (4/π)·λ²·ln λ²` — the
time–frequency Shannon number of the box (Landau–Pollak; Slepian–Pollak;
Landau–Widom). The coordinate is forced, not posited.
```bash
python3 scripts/reproduce.py shannon          # server-grade (λ²=100 to saturation)
```
Expected: saturation at `N/(λ²·ln λ²) ≈ 2.0–2.3`.

### C11 — Prime ceiling leading coefficient `K = 4π/ln10` (§6) · **T2** · *derived + validated*

The eigenvalue floor `D_eig = −log₁₀ ε∞(λ)` ties to the principal prolate
spheroidal eigenvalue; the asymptotic gives `D_eig = Kλ² − (9/2ln10)·ln λ² − C₀`,
with `K = 4π/ln10` exact and parameter-free, `9/2` the Fuchs index, and
`C₀ = log₁₀(2¹⁴√2·π⁵/3) = 6.3736…`. The matching floor the law consumes sits a
few digits below (C12).
```bash
python3 scripts/reproduce.py prime-anchor     # server-grade (~20-40 min)
```
Expected: `D_Primes(100) = 526.08`.

### C12 — Matching floor / two-floor structure (§6) · **T4** · *empirical*

The matching floor the minimum actually consumes, `D_Primes = Kλ² −
P_m·log₁₀λ² − c_m` with `P_m ≈ 5`, `c_m ≈ 9.5`, sits a few digits below the
eigenvalue floor `D_eig`; the difference is the *conversion gap*
`conv = D_eig − D_Primes`. At λ²=200 the saturated measurement sits at the
matching floor, confirming the two-floor structure at the largest cutoff measured.
```bash
python3 scripts/reproduce.py matching-floor   # server-grade (multi-hour, HP-1250)
```
Expected: `D_Primes(200) ≈ 1070.4`; matching floor `1070.5`; eigenvalue floor
`1074.77`; gap ≈ 4.3.

### C13 — The floor is smooth, not a prime staircase (§6) · **T2** · *empirical*

Sweeping `λ²` in unit steps (`N`, `P` above floor) gives a smooth rise of
`≈ 5.3` digits per unit `λ²`; prime-power entries are statistically
indistinguishable from non-prime entries.
```bash
python3 scripts/reproduce.py prime-smooth     # add --quick for λ²∈[4,15]
```

### C14 — Convergence criterion and the prime bottleneck (§7, Prop. 2) · **T1** · *derived*

For every fixed `λ²`, `sup_{N,P} D = D_Primes(λ²) < ∞`: no basis size or
precision reaches the zero, so convergence to `γ₁` forces `λ² → ∞`. And
`ν₁ → γ₁` iff all three budgets diverge. *Proof: §7.* Demonstration:
```bash
python3 scripts/reproduce.py bottleneck
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
cargo build --release --features hp
```

### Running

```bash
# one claim
python3 scripts/reproduce.py precision-slope

# everything, light configs only (minutes on a laptop / WSL2)
python3 scripts/reproduce.py all --quick

# everything, including server-grade claims (hours, large memory)
python3 scripts/reproduce.py all
```

Each command prints a compact **measured vs expected** verdict.

### Compute tiers

| Tier | Claims | Cost |
|---|---|---|
| **Light** (WSL2, minutes) | C1, C2, C3, C7, C13 (`--quick`), C14, and λ²≤25 of C4/C8/C9 | laptop-friendly |
| **Server** (hours, large memory) | C10 (Shannon), C11 (λ²=100 floor), C12 (λ²=200 floor), and λ²≥50 of C4/C8/C9 | excluded by `--quick` |

`--quick` runs only the light tier; server-grade claims print a clear banner and
are skipped.

### Notes

- `D` is read as the matching-digit count of the **first** eigenvalue versus the
  reference `γ₁` in `data/zeta_zeros.json` (≈2500 digits).
- High-precision quadrature/eigenvector fixtures are cached; by default the
  binary fetches them (`XC_CACHE_MODE=fetch`). Set `XC_CACHE_MODE=off` for pure
  compute or `local` for disk-only.
- The per-λ² `q`/`c` fit is a small grid search over the `tanh` ramp; values
  reproduce Table 1 to within fit scatter on sparse sweeps.

---

## Repository layout

```
paper.tex / paper.pdf       the manuscript
paper_v1.0.pdf              frozen snapshot matching the Zenodo v1.0 deposit
src/main.rs                 the `measure` binary (CCM construction + matching digits)
scripts/reproduce.py        one-command claim reproduction driver
data/zeta_zeros.json        reference Riemann zeros (~2500 digits)
data/*_cache/               cached HP fixtures (regeneratable; .gitkeep preserved)
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
