# A Quantitative Convergence Law for the Connes–Consani–Moscovici Zeta Spectral Triple

High-precision experiments and conditional estimates for the cutoff, mode,
precision, and zero-index dependence of the CCM construction.

**Author:** Ronnie Andrews, Jr. · [ORCID](https://orcid.org/0009-0003-9724-3104) ·
[randrewsmath@gmail.com](mailto:randrewsmath@gmail.com)<br>
**Software:** v1.2 (package 1.2.0), using Xcelerator Toolkit v0.17.0<br>
**Manuscript:** the working continuation is newer than the deposited edition.
[Zenodo concept DOI](https://doi.org/10.5281/zenodo.20938200)

The paper separates a rigorous error-budget inequality from empirical models
for the finite spectral error. It also develops finite source and root
certificates under their stated hypotheses. A uniform, parameter-only
convergence law in `C = λ²`, `N`, `P`, and the zero index remains open.

This repository contains the manuscript, Rust numerical driver, and individual
reproduction scripts. The Toolkit migration does **not** revalidate the
historical measurements. Current campaign status and the limits of the
historical results are recorded in [results and scope](docs/RESULTS.md).

## Read and reproduce

| Resource | Contents |
|---|---|
| [Manuscript PDF](paper.pdf) · [LaTeX source](paper.tex) | Derivations, historical measurements, finite certificates, and rigor ledger |
| [Claim catalog](docs/CLAIMS.md) | All 14 numbered claims and their scientific scope |
| [Script catalog](scripts/README.md) | Individual numerical experiments, exact grids, and execution options |
| [Reproduction guide](docs/REPRODUCTION.md) | Build, execution controls, journals, reuse, and publication |
| [Results and scope](docs/RESULTS.md) | Historical reference values, unvalidated configurations, and open obligations |

## Run one claim

Use Linux or WSL2 for high-precision builds, with Bash, Git, Python 3, and
current stable Rust. Numerical calculations are implemented in Rust; the
existing Python driver coordinates sweeps and summarizes measurements.

```bash
sudo apt-get install build-essential m4 libgmp-dev libmpfr-dev libmpc-dev
bash scripts/claim2_precision_slope.sh --plan
bash scripts/claim2_precision_slope.sh --validate-only
bash scripts/claim2_precision_slope.sh
```

Claim 2 holds `C=50, N=400` fixed and sweeps 50, 100, 150, and 200 requested
decimal digits. It checks the finite precision-slope model against the stated
acceptance thresholds. A successful finite fit does not establish an
end-to-end error theorem. Begin with one individual claim before attempting
the larger saturation sweeps; no full-campaign runtime is promised.

The scripts default to **Ultra** diagnostic capture, with sector-gap
certificates off. Some diagnostics need explicit external inputs; a standalone
run without them can retain incomplete capture. See the
[input and capture guide](docs/REPRODUCTION.md#capture-and-external-inputs).
Remote publication is off unless explicitly requested.

The exact Toolkit revision is pinned in [Cargo.toml](Cargo.toml) and
[Cargo.lock](Cargo.lock):
`97e9445ebbf1844a7d60b5141d3fb737fe9f00dd`.
Historical measurements retain their original source and arithmetic scope.
Requested decimal precision, source precision, and adaptive evaluation
precision are different quantities; a fixed 64-bit reserve does not describe
every operation in the current Toolkit.

## Interpret the evidence

Read computational completeness, finite numerical checks, diagnostic
qualification, and publication status separately. A completed artifact can
retain conditional or unresolved rows. A finite comparison can fail without
implying a faulty computation. Neither outcome settles an asymptotic claim.

The central one-sided bound is

```text
D ≥ min(D_precision, D_modes, D_cutoff) − log10(3).
```

It follows from a triangle inequality for the separately defined errors.
A matching upper bound needs quantitative noncancellation. At a fixed cutoff,
the manuscript's branch-convergence result assumes a simple isolated even
ground state, a simple isolated limiting transform zero different from the
reference zero, and vanishing numerical perturbation. The finite scripts do
not certify all those continuum hypotheses.

The `C log C` crossover is a consequence of two candidate rate inputs. It is
Shannon-like; an exact identification with a classical time–band limiting
operator remains open. The fitted onset coefficient and the crossover
multiplier are distinct. See the manuscript's rigor ledger for the scope of
each statement.

## Repository layout

```text
paper.tex / paper.pdf       working manuscript and its retained PDF
sections/ / figures/       included manuscript material
paper_v1.1.tex / .pdf       historical v1.1 manuscript
paper_v1.0.pdf              historical v1.0 manuscript
src/main.rs                Rust measurement and artifact driver
scripts/claim*.sh           individually runnable numerical experiments
scripts/reproduce.py        sweep coordination and numerical summaries
docs/                      public reproduction and evidence guidance
tests/                     software checks
claim-runs/                ignored fresh claim results and logs
outputs/                   ignored legacy local results
```

## Related work

- [Independent Reproduction and Convergence Analysis of the CCM Zeta Spectral Triple](https://github.com/TeamXcelerator/ccm-reproduction-and-convergence)
  · [concept DOI](https://doi.org/10.5281/zenodo.20427499).
- [Convergence Claims for the CCM Construction: An Empirical Reassessment](https://github.com/TeamXcelerator/ccm-convergence-rate-falsifications)
  · [concept DOI](https://doi.org/10.5281/zenodo.20427673).
- [Xcelerator Toolkit](https://github.com/TeamXcelerator/xcelerator-toolkit),
  the shared arbitrary-precision numerical library.

## Citation

Cite the manuscript edition used. For a reproduction, also retain the exact
software commit, Toolkit revision, configuration, and result identity. The
working Git tree and the latest Zenodo deposit can contain different material.

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

See [LICENSE](LICENSE). Source-available for verification and study; the
source-code license restricts modification, redistribution, and commercial
use. The accompanying manuscript is licensed under CC BY-NC-ND 4.0.

"Team Xcelerator Inc." is a registered trademark of Team Xcelerator Inc.
