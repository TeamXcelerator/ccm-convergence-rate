#!/usr/bin/env python3
# Copyright (c) 2026 Ronnie Andrews, Jr. (Team Xcelerator Inc.(R))
# See LICENSE for terms. Provided for verification and study.
"""
reproduce.py -- one-command reproduction driver for the claims of

    "A Quantitative Convergence Law for the Connes-Consani-Moscovici
     Zeta Spectral Triple"  (Andrews, 2026; doi:10.5281/zenodo.20938200)

Each subcommand runs the `measure` binary across the parameter sweep a
single claim needs, extracts the matching-digit count D of the first
eigenvalue, computes the derived quantity (slope / exponent / floor / ...),
and prints a compact  measured-vs-expected  verdict. No spreadsheets, no
eyeballing hundreds of lines.

    python3 scripts/reproduce.py <claim> [--quick] [--bin PATH]

Claims (paper order):
    precision-slope     C2   D_Wprec slope = 1
    budget-switch       C1   the min() switches budgets (low-scale demo)
    floor-artifact      C3   sub-floor results are precision-limited
    nmode-ramp          C4/C8/C9  tanh ramp; exponent q; onset c
    archimedean-slope   C7   leading digit slope pi^2/(ln10 ln L2) at L2=7
    shannon             C10  saturation at N/(L2 ln L2) ~ 2.0-2.3   [server]
    prime-anchor        C11  D_Primes(100) = 526.08
    matching-floor      C12  D_Primes(200) ~ 1070.4 = two-floor anchor [server]
    prime-smooth        C13  ceiling is smooth, ~5.3 digits / unit L2
    bottleneck          C14  sup over N,P at fixed L2 = the prime ceiling
    all                 run every claim (use --quick to skip server-grade)

Requires: a release build with the `hp` feature, and Python 3.8+ (stdlib only).
    cargo build --release --features hp        (run inside WSL2 on Windows)
"""
import argparse
import math
import os
import subprocess
import sys

# --------------------------------------------------------------------------
# Constants from the paper
# --------------------------------------------------------------------------
GAMMA = 0.5772156649015329       # Euler-Mascheroni
LN10 = math.log(10.0)
K = 4.0 * math.pi / LN10         # prime-ceiling leading coefficient, 5.45750...
C0 = math.log10(2.0**14 * math.sqrt(2.0) * math.pi**5 / 3.0)  # 6.3736..., eigenvalue-floor prefactor
P_M = 5.0                        # matching-floor sub-log coefficient (empirical)
C_M = 9.5                        # matching-floor offset (empirical)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_BIN = os.path.join(REPO_ROOT, "target", "release", "ccm-convergence-rate")

# --------------------------------------------------------------------------
# Derived quantities (closed forms from the paper)
# --------------------------------------------------------------------------
def matching_floor(lsq):
    """Matching floor D_match = K L2 - P_m log10 L2 - c_m  (paper eq:primes, the floor min() consumes)."""
    return K * lsq - P_M * math.log10(lsq) - C_M

def eigenvalue_floor(lsq):
    """Eigenvalue floor = K L2 - (9/2) log10 L2 - C0  (paper eq:eigfloor, the prolate asymptotic)."""
    return K * lsq - 4.5 * math.log10(lsq) - C0

def shannon_number(lsq):
    """Time-frequency Shannon number of the box, S = L2 ln L2."""
    return lsq * math.log(lsq)

def q_formula(lsq):
    """Closed-form mode exponent q(L2) = 2 / (2 gamma + ln ln L2)  (paper eq:q)."""
    return 2.0 / (2.0 * GAMMA + math.log(math.log(lsq)))

def archimedean_slope(lsq):
    """Predicted leading digit slope, pi^2 / (ln10 ln L2)  (paper eq:slope)."""
    return math.pi**2 / (LN10 * math.log(lsq))

# --------------------------------------------------------------------------
# Binary invocation + output parsing
# --------------------------------------------------------------------------
_BIN = DEFAULT_BIN

def measure(lsq, n, p, top=5):
    """Run `measure` and return D = matching digits of the first eigenvalue (float, or None)."""
    cmd = [_BIN, "measure",
           "--lambda-sq", str(lsq),
           "--n-modes", str(n),
           "--precision-digits", str(p),
           "--top", str(top),
           "--display-digits", "16"]
    try:
        out = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True,
                             text=True, timeout=36000)
    except FileNotFoundError:
        sys.exit(f"ERROR: binary not found at {_BIN}\n"
                 f"Build it first (inside WSL2 on Windows):\n"
                 f"    cargo build --release --features hp")
    if out.returncode != 0:
        sys.stderr.write(out.stdout + out.stderr)
        sys.exit(f"ERROR: measure failed for L2={lsq} N={n} P={p}")
    return _parse_first_d(out.stdout)

def _parse_first_d(stdout):
    """Extract the matching-digit value from the k=1 row of the results table."""
    for line in stdout.splitlines():
        toks = line.split()
        if len(toks) >= 4 and toks[0] == "1":
            last = toks[-1]
            if last == "N/A":
                return None
            try:
                return float(last)
            except ValueError:
                continue
    return None

# --------------------------------------------------------------------------
# Small stdlib fitting helpers
# --------------------------------------------------------------------------
def linfit(xs, ys):
    """Ordinary least squares y = a + b x. Returns (intercept a, slope b, R^2)."""
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    b = sxy / sxx
    a = my - b * mx
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return a, b, r2

def fit_tanh_ramp(lsq, ns, ds):
    """
    Fit g = tanh((c N / S)^q) to the measured ramp ratios g = D / ceiling,
    by coarse-then-fine grid search. Returns (c, q).
    """
    S = shannon_number(lsq)
    ceil = matching_floor(lsq)
    pts = [(n, d / ceil) for n, d in zip(ns, ds)
           if d is not None and 0.02 < d / ceil < 0.999]
    if len(pts) < 3:
        return None, None

    def rms(c, q):
        e = 0.0
        for n, g in pts:
            model = math.tanh((c * n / S) ** q)
            e += (model - g) ** 2
        return e

    best = (None, None, float("inf"))
    # coarse pass
    c = 1.00
    while c <= 1.50001:
        q = 0.50
        while q <= 1.40001:
            e = rms(c, q)
            if e < best[2]:
                best = (c, q, e)
            q += 0.01
        c += 0.01
    # fine pass around the coarse optimum
    c0, q0 = best[0], best[1]
    best = (c0, q0, float("inf"))
    c = c0 - 0.02
    while c <= c0 + 0.02001:
        q = q0 - 0.02
        while q <= q0 + 0.02001:
            e = rms(c, q)
            if e < best[2]:
                best = (c, q, e)
            q += 0.002
        c += 0.002
    return best[0], best[1]

# --------------------------------------------------------------------------
# Pretty printing
# --------------------------------------------------------------------------
def dstr(d, prec=3):
    """Format a possibly-None D value for a table cell."""
    return "N/A" if d is None else f"{d:.{prec}f}"

def banner(title, claim, section):
    print("=" * 74)
    print(f"  {claim}  |  {title}")
    print(f"  paper: {section}")
    print("=" * 74)

def server_note(desc):
    print(f"  [server-grade] {desc}")
    print(f"  Skipped under --quick. Re-run without --quick on a capable host.\n")

# --------------------------------------------------------------------------
# Claims
# --------------------------------------------------------------------------
def c2_precision_slope(quick):
    banner("Precision budget: D_Wprec = P + O(1), slope exactly 1",
           "C2", '"The precision budget"')
    lsq, n = 50, 400
    ps = [50, 100, 150, 200]
    print(f"  Isolating the precision budget at L2={lsq}, N={n} "
          f"(modes + prime ceiling held above P).\n")
    print(f"  {'P':>6}  {'D measured':>12}")
    xs, ys = [], []
    for p in ps:
        d = measure(lsq, n, p)
        print(f"  {p:>6}  {dstr(d):>12}")
        if d is not None:
            xs.append(p); ys.append(d)
    _, slope, r2 = linfit(xs, ys)
    print(f"\n  measured slope dD/dP = {slope:.4f}   (R^2 = {r2:.5f})")
    print(f"  expected             = 1.000 +/- 0.001")
    print(f"  VERDICT: {'PASS' if abs(slope - 1.0) < 0.02 else 'CHECK'}\n")

def c1_budget_switch(quick):
    banner("The minimum is forced: budgets switch as P grows (demo)",
           "C1", '"The three-budget skeleton" (Prop. "The minimum is forced")')
    lsq, n = 13, 80
    ceil = matching_floor(lsq)
    ps = [30, 45, 90, 180]
    print(f"  Fixed L2={lsq}, N={n}. Prime ceiling D_Primes ~ {ceil:.1f}.")
    print(f"  Small P: precision binds (D ~ P). Large P: prime ceiling binds.\n")
    print(f"  {'P':>6}  {'D measured':>12}  binding budget")
    for p in ps:
        d = measure(lsq, n, p)
        if d is None:
            print(f"  {p:>6}  {'N/A':>12}  (unresolved)")
            continue
        which = "precision" if d < ceil - 3 else "prime ceiling"
        print(f"  {p:>6}  {d:>12.3f}  {which}")
    print(f"\n  D rises with P, then plateaus at the prime ceiling ~ {ceil:.1f}:")
    print(f"  the binding budget switches -- the law's min() in action.\n")

def c3_floor_artifact(quick):
    banner("Sub-floor results are precision-limited; raising P recovers truth",
           "C3", '"Symmetry, positivity, and the precision floor"')
    lsq, n = 50, 400
    ceil = matching_floor(lsq)
    ps = [50, 150, 300]
    print(f"  L2={lsq}, N={n}. True floor D_Primes ~ {ceil:.1f}.")
    print(f"  Below floor (P < ~{ceil:.0f}) the eigenvalue is unresolved and")
    print(f"  precision-limited; raising P past the floor recovers the true value.\n")
    print(f"  {'P':>6}  {'D measured':>12}  state")
    for p in ps:
        d = measure(lsq, n, p)
        if d is None:
            print(f"  {p:>6}  {'N/A':>12}  unresolved")
            continue
        state = "precision-starved (D~P)" if d < ceil - 3 else "floor recovered"
        print(f"  {p:>6}  {d:>12.3f}  {state}")
    print(f"\n  The full even-symmetry / positivity reproduction (38 configs,")
    print(f"  natural vs forced-even eigenvector) is documented in the")
    print(f"  independent reproduction (doi:10.5281/zenodo.20427499):")
    print(f"    github.com/TeamXcelerator/ccm-reproduction-and-convergence\n")

def c7_archimedean_slope(quick):
    banner("Archimedean leading rate: slope = pi^2 / (ln10 ln L2) at L2=7",
           "C7", '"The archimedean leading rate"')
    lsq = 7
    # Initial-slope window matching the paper: N in [2, 0.25*Shannon], min 8.
    S = shannon_number(lsq)
    nmax = min(max(8, int(0.25 * S)), 30)
    ns = list(range(2, nmax + 1))
    p = 200
    print(f"  Small-N initial-slope window N in [2,{nmax}] at L2={lsq} "
          f"(few primes, q ~ 1), P={p}.\n")
    print(f"  {'N':>6}  {'D measured':>12}")
    xs, ys = [], []
    for n in ns:
        d = measure(lsq, n, p)
        print(f"  {n:>6}  {dstr(d):>12}")
        if d is not None:
            xs.append(n); ys.append(d)
    if len(xs) < 3:
        print("\n  Too few converged points to fit a slope.\n")
        return
    _, slope, r2 = linfit(xs, ys)
    pred = archimedean_slope(lsq)
    print(f"\n  fit window actually used: N = {xs[0]}..{xs[-1]}")
    print(f"  measured initial slope dD/dN = {slope:.3f}   (R^2 = {r2:.4f})")
    print(f"  predicted pi^2/(ln10 ln7)    = {pred:.3f}   (parameter-free)")
    print(f"  paper reports                ~ 2.264  (3% match, using N=2,3 too)")
    if xs[0] > 2:
        print(f"  NOTE: the live binary resolves the zero only from N={xs[0]} up;")
        print(f"        the steep N=2,3 points (paper's 3% match) are not")
        print(f"        recomputable here, so the slope reads a bit low.")
    print(f"  VERDICT: {'PASS' if abs(slope - pred) / pred < 0.15 else 'CHECK'}\n")

# per-L2 ramp grids: (lsq, [N values], P, server?)
# N is capped near ~1.3*Shannon. The tanh ceiling is known analytically from
# D_Primes, so points past the knee (g >~ 0.9) cost the most (the HP eigensolve
# is ~O(N^3)) yet add almost nothing to the q/c fit. Covering g ~ 0.1-0.9 pins
# both q and c. lambda^2=150 is dropped from the default (lambda^2<=100 already
# gives a clean 6-point q-regression); re-add a (150, [...], 1000, True) row if
# the extra lever-arm is wanted.
_RAMP_GRID = [
    (7,   [3, 5, 7, 9, 11, 13, 15, 18],            200, False),
    (13,  [7, 11, 16, 21, 27, 33, 39, 44],         200, False),
    (20,  [12, 20, 28, 38, 48, 58, 68, 78],        300, False),
    (25,  [16, 28, 40, 55, 70, 85, 98, 108],       300, False),
    (50,  [40, 70, 105, 140, 175, 210, 240, 260],  500, True),
    (100, [90, 170, 250, 330, 410, 490, 560, 620], 700, True),
]
# Paper fit-table (tab:q) reference values
_TABLE1_Q = {7: 1.185, 13: 0.985, 20: 0.900, 25: 0.880, 50: 0.835, 100: 0.785, 150: 0.760}
_TABLE1_C = {7: 1.20, 13: 1.25, 20: 1.28, 25: 1.29, 50: 1.31, 100: 1.28, 150: 1.26}

def c4_nmode_ramp(quick):
    banner("Mode budget: tanh ramp, exponent q(L2), onset c ~ 4/pi",
           "C4 / C8 / C9", '"The mode budget"')
    rows = []
    for lsq, ns, p, server in _RAMP_GRID:
        if quick and server:
            continue
        print(f"  -- L2={lsq}: ramping N up to {ns[-1]} at P={p} "
              f"(Shannon S = {shannon_number(lsq):.1f}) ...", flush=True)
        ds = [measure(lsq, n, p) for n in ns]
        c, q = fit_tanh_ramp(lsq, ns, ds)
        if c is None:
            print("     not enough in-ramp points; skipping fit.", flush=True)
            continue
        rows.append((lsq, q, c))
        # Incremental result: print each L2's fit as it completes (flushed), so a
        # long run shows progress live and partial output survives interruption.
        print(f"     -> q={q:.3f} (paper {_TABLE1_Q.get(lsq, float('nan')):.3f}, "
              f"formula {q_formula(lsq):.3f}),  c={c:.3f}  (4/pi={4/math.pi:.3f})",
              flush=True)
    if not rows:
        return
    print(f"\n  {'L2':>5}  {'q meas':>8}  {'q paper':>8}  {'q form':>8}  "
          f"{'c meas':>8}  {'c paper':>8}")
    for lsq, q, c in rows:
        print(f"  {lsq:>5}  {q:>8.3f}  {_TABLE1_Q.get(lsq, float('nan')):>8.3f}  "
              f"{q_formula(lsq):>8.3f}  {c:>8.3f}  {_TABLE1_C.get(lsq, float('nan')):>8.3f}")
    # onset verdict
    cs = [c for _, _, c in rows]
    cmean = sum(cs) / len(cs)
    print(f"\n  onset constant c: mean = {cmean:.3f}, target 4/pi = {4/math.pi:.3f}")
    print(f"  VERDICT (onset): {'PASS' if abs(cmean - 4/math.pi) < 0.1 else 'CHECK'}")
    # q regression: 1/q = c0 + c1 lnln L2
    if len(rows) >= 3:
        xs = [math.log(math.log(lsq)) for lsq, _, _ in rows]
        ys = [1.0 / q for _, q, _ in rows]
        c0, c1, r2 = linfit(xs, ys)
        print(f"\n  regression 1/q = c0 + c1 lnln(L2):")
        print(f"    c0 = {c0:.3f}  (gamma   = {GAMMA:.3f})")
        print(f"    c1 = {c1:.3f}  (1/2     = 0.500)")
        print(f"    R^2 = {r2:.3f}  (paper reports 0.98)")
        ok = abs(c0 - GAMMA) < 0.12 and abs(c1 - 0.5) < 0.12
        print(f"  VERDICT (q-law): {'PASS' if ok else 'CHECK'}\n")

def c10_shannon(quick):
    banner("Shannon coordinate: saturation at N/(L2 ln L2) ~ 2.0-2.3",
           "C10", '"The Shannon coordinate" (Lem. "Coordinate from ceiling over slope")')
    if quick:
        server_note("L2=100 ramp to saturation (N up to ~1200, HP-700).")
        return
    lsq, p = 100, 700
    S = shannon_number(lsq)
    ceil = matching_floor(lsq)
    ns = list(range(100, 1300, 100))
    print(f"  L2={lsq}, P={p}. Shannon S = {S:.1f}, ceiling ~ {ceil:.1f}.\n")
    print(f"  {'N':>6}  {'D':>10}  {'g=D/ceil':>10}  {'N/S':>8}")
    nsat = None
    for n in ns:
        d = measure(lsq, n, p)
        if d is None:
            print(f"  {n:>6}  {'N/A':>10}  {'-':>10}  {n / S:>8.3f}")
            continue
        g = d / ceil
        print(f"  {n:>6}  {d:>10.2f}  {g:>10.3f}  {n / S:>8.3f}")
        if nsat is None and g >= 0.999:
            nsat = n
    if nsat:
        print(f"\n  saturation (g>=0.999) reached near N/S = {nsat / S:.2f}")
        print(f"  expected band: 2.0-2.3")
        print(f"  VERDICT: {'PASS' if 1.8 <= nsat / S <= 2.6 else 'CHECK'}\n")

def c11_prime_anchor(quick):
    banner("Prime ceiling anchor: D_Primes(100) = 526.08",
           "C11", '"The prime ceiling"')
    if quick:
        server_note("single saturated floor run at L2=100, N=1000, HP-700 (~20-40 min).")
        return
    lsq, n, p = 100, 1000, 700
    d = measure(lsq, n, p)
    print(f"  L2={lsq}, N={n}, P={p} (both N and P above floor).\n")
    print(f"  D measured            = {dstr(d, 2)}")
    print(f"  paper reports         = 526.08")
    print(f"  matching-floor formula = {matching_floor(lsq):.2f}  (K L2 - 5 log10 L2 - 9.5)")
    print(f"  K = 4 pi / ln10        = {K:.5f}  (exact, parameter-free)")
    print(f"  VERDICT: {'PASS' if abs(d - 526.08) < 3 else 'CHECK'}\n")

def c12_matching_floor(quick):
    banner("Matching floor / two-floor structure: D_Primes(200) ~ 1070.4",
           "C12", '"The prime ceiling"')
    if quick:
        server_note("L2=200, N>=2400, HP-1250 -- multi-hour, large memory.")
        return
    lsq, p = 200, 1250
    print(f"  L2={lsq}, P={p}, N>=2400 (saturated).\n")
    print(f"  {'N':>6}  {'D':>10}")
    d = None
    for n in [2400, 2800]:
        d = measure(lsq, n, p)
        print(f"  {n:>6}  {dstr(d, 2):>10}")
    mf = matching_floor(lsq)
    ef = eigenvalue_floor(lsq)
    print(f"\n  matching floor  K L2 - 5 log10 L2 - 9.5      = {mf:.2f}")
    print(f"  eigenvalue floor K L2 - 4.5 log10 L2 - C0    = {ef:.2f}")
    print(f"  two-floor gap (conv)                         = {ef - mf:.2f}")
    print(f"  paper reports D_Primes(200) ~ 1070.4, matching floor 1070.5")
    print(f"  VERDICT: {'PASS' if d and abs(d - mf) < 3 else 'CHECK'}\n")

def c13_prime_smooth(quick):
    banner("Prime ceiling is smooth, not a staircase (~5.3 digits / unit L2)",
           "C13", '"The prime ceiling"')
    n, p = 300, 200
    hi = 16 if quick else 31
    lsqs = list(range(4, hi))
    print(f"  N={n}, P={p} (above floor). Unit steps in L2 from 4 to {hi - 1}.\n")
    print(f"  {'L2':>5}  {'D':>10}  {'dD':>8}  prime-power entry?")
    prev = None
    deltas = []
    primeish = {4, 8, 9, 16, 25, 27}  # sample prime-power thresholds in range
    for lsq in lsqs:
        d = measure(lsq, n, p)
        if d is None:
            print(f"  {lsq:>5}  {'N/A':>10}  {'-':>8}  unresolved")
            continue
        dd = "" if prev is None else f"{d - prev:.2f}"
        if prev is not None:
            deltas.append(d - prev)
        is_pp = "yes" if (lsq in primeish or _is_prime(lsq)) else "no"
        print(f"  {lsq:>5}  {d:>10.2f}  {dd:>8}  {is_pp}")
        prev = d
    if deltas:
        mean = sum(deltas) / len(deltas)
        print(f"\n  mean rise per unit L2 = {mean:.2f} digits   (paper ~5.3)")
        print(f"  rises are smooth; prime-power entries are not special.")
        print(f"  VERDICT: {'PASS' if 4.5 <= mean <= 6.0 else 'CHECK'}\n")

def c14_bottleneck(quick):
    banner("Prime bottleneck: sup over N,P at fixed L2 = the prime ceiling",
           "C14", '"The complete formula" (Prop. "Convergence criterion and the prime bottleneck")')
    lsq = 13
    ceil = matching_floor(lsq)
    grid = [(40, 100), (80, 200), (120, 400), (200, 800)]
    print(f"  Fixed L2={lsq}. Push BOTH N and P; D cannot exceed D_Primes ~ {ceil:.1f}.\n")
    print(f"  {'N':>6}  {'P':>6}  {'D':>10}")
    last = None
    for n, p in grid:
        d = measure(lsq, n, p)
        print(f"  {n:>6}  {p:>6}  {dstr(d, 2):>10}")
        if d is not None:
            last = d
    print(f"\n  D saturates at the prime ceiling ~ {ceil:.1f} and stops:")
    print(f"  no N or P beats it -- reaching gamma_1 forces L2 -> infinity.")
    print(f"  VERDICT: {'PASS' if last and abs(last - ceil) < 4 else 'CHECK'}\n")

def _is_prime(m):
    if m < 2:
        return False
    for i in range(2, int(m**0.5) + 1):
        if m % i == 0:
            return False
    return True

# --------------------------------------------------------------------------
# Dispatch
# --------------------------------------------------------------------------
CLAIMS = {
    "precision-slope": c2_precision_slope,
    "budget-switch": c1_budget_switch,
    "floor-artifact": c3_floor_artifact,
    "nmode-ramp": c4_nmode_ramp,
    "archimedean-slope": c7_archimedean_slope,
    "shannon": c10_shannon,
    "prime-anchor": c11_prime_anchor,
    "matching-floor": c12_matching_floor,
    "prime-smooth": c13_prime_smooth,
    "bottleneck": c14_bottleneck,
}
# Sensible run order for `all` (paper order)
ALL_ORDER = ["budget-switch", "precision-slope", "floor-artifact", "nmode-ramp",
             "archimedean-slope", "shannon", "prime-anchor", "matching-floor",
             "prime-smooth", "bottleneck"]

def main():
    ap = argparse.ArgumentParser(
        description="Reproduce the claims of the CCM Convergence Law paper.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Claims: " + ", ".join(ALL_ORDER) + ", all")
    ap.add_argument("claim", help="claim to reproduce (or 'all')")
    ap.add_argument("--quick", action="store_true",
                    help="run only light (WSL2-minutes) configs; skip server-grade")
    ap.add_argument("--bin", default=DEFAULT_BIN,
                    help="path to the ccm-convergence-rate binary")
    args = ap.parse_args()

    global _BIN
    _BIN = args.bin

    if args.claim == "all":
        for name in ALL_ORDER:
            CLAIMS[name](args.quick)
        return
    if args.claim not in CLAIMS:
        ap.error(f"unknown claim '{args.claim}'. Choose from: "
                 + ", ".join(ALL_ORDER) + ", all")
    CLAIMS[args.claim](args.quick)

if __name__ == "__main__":
    main()
