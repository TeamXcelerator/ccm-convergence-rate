#!/usr/bin/env python3
"""One-shot source-hash-guarded driver edits; removed after test qualification.
Owner authorized the CCM audit implementation; AI-generated assistance.
"""
from pathlib import Path
import hashlib

root = Path(__file__).resolve().parents[1]
path = root / "scripts/reproduce.py"
raw = path.read_bytes()
assert hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == "2f5797e764a48ae4f86758137673f7a8c4c81ed5"
s = raw.decode()

def once(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError(f"ambiguous driver edit: {old[:100]!r}")
    return text.replace(old, new, 1)

s = once(s, "import time\n", """import time

# Resolve the sibling module for direct CLI invocation and importlib-based tests.
_SCRIPT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIRECTORY not in sys.path:
    sys.path.insert(0, _SCRIPT_DIRECTORY)
from scientific_results import (
    qualified_digits, scientific_verdict, stamp_measurement,
    validate_root_window, verify_measurement_provenance,
)
""")
s = once(s, "_MEASUREMENTS = []\n", """_MEASUREMENTS = []
_CLAIM_VERDICTS = []
_CLAIM_SKIPPED = False
_QUALIFICATION_ISSUES = []
""")
s = once(s, "def _load_measurement(path, lsq, n, p, zero_count):\n", """def _load_measurement(path, lsq, n, p, zero_count):
    verify_measurement_provenance(path, _BIN, REPO_ROOT)
""")
s = once(s, "    return report\n\ndef _selected_digits(report):", """    validate_root_window(report, _FIRST_ZERO_INDEX, zero_count)
    return report

def _selected_digits(report):""")
s = once(s, "            return root[\"matching_digits_f64\"]\n    return None", """            digits = qualified_digits(root)
            if digits is None:
                _QUALIFICATION_ISSUES.append(
                    f\"zero {_ANALYSIS_ZERO_INDEX}: {root.get('status', 'missing status')} \"
                    \"or nonfinite matching digits; retained but excluded from fitting\"
                )
            return digits
    _QUALIFICATION_ISSUES.append(f\"analysis zero {_ANALYSIS_ZERO_INDEX} is not retained\")
    return None""")
s = once(s, "    effective_zero_count = min(requested_zero_count, n)", """    available_count = n
    if _ROOT_ACQUISITION == \"independent\":
        available_count = max(0, n - _FIRST_ZERO_INDEX + 1)
    effective_zero_count = min(requested_zero_count, available_count)
    if effective_zero_count == 0:
        _QUALIFICATION_ISSUES.append(\"independent ordinal window exceeds finite source capacity\")
        return None""")
s = once(s, "    try:\n        report = _load_measurement(result_path, lsq, n, p, effective_zero_count)", """    try:
        stamp_measurement(result_path, _BIN, REPO_ROOT)
        report = _load_measurement(result_path, lsq, n, p, effective_zero_count)""")
# Evenness resume requires the same binary/source/content receipt protection.
start = s.index("def measure_evenness(")
end = s.index("# Small stdlib fitting helpers", start)
part = s[start:end]
part = once(part, "        try:\n            with open(result_path", "        try:\n            verify_measurement_provenance(result_path, _BIN, REPO_ROOT)\n            with open(result_path")
part = once(part, "except (OSError, KeyError, json.JSONDecodeError):", "except (OSError, ValueError, KeyError, json.JSONDecodeError):")
part = once(part, "    with open(result_path, \"r\", encoding=\"utf-8\") as stream:\n        report = json.load(stream)\n    _MEASUREMENTS.append", "    stamp_measurement(result_path, _BIN, REPO_ROOT)\n    with open(result_path, \"r\", encoding=\"utf-8\") as stream:\n        report = json.load(stream)\n    _MEASUREMENTS.append")
s = s[:start] + part + s[end:]
s = once(s, "    n = len(xs)\n    mx = sum(xs) / n", """    n = len(xs)
    if n < 2 or len(ys) != n or any(not math.isfinite(v) for v in list(xs) + list(ys)):
        _QUALIFICATION_ISSUES.append(\"linear fit has insufficient or nonfinite observations\")
        return float(\"nan\"), float(\"nan\"), float(\"nan\")
    mx = sum(xs) / n""")
s = once(s, "    b = sxy / sxx", """    if sxx == 0:
        _QUALIFICATION_ISSUES.append(\"linear fit has no variation in its independent coordinate\")
        return float(\"nan\"), float(\"nan\"), float(\"nan\")
    b = sxy / sxx""")
start = s.index("def verdict(condition):")
end = s.index("def banner(", start)
s = s[:start] + """def verdict(condition):
    \"\"\"Record the scientific verdict separately from successful execution.\"\"\"
    if _ANALYSIS_ZERO_INDEX != 1:
        _CLAIM_VERDICTS.append(\"EXPLORATORY\")
        return \"EXPLORATORY\"
    _CLAIM_VERDICTS.append(\"PASS\" if condition else \"FAIL\")
    # Preserve the historical human-facing label; the JSON verdict is FAIL.
    return \"PASS\" if condition else \"CHECK\"

""" + s[end:]
s = once(s, "def server_note(desc):\n", "def server_note(desc):\n    global _CLAIM_SKIPPED\n    _CLAIM_SKIPPED = True\n")
s = once(s, "        _FIRST_ZERO_INDEX,\n        _ROOT_ACQUISITION,", "        _FIRST_ZERO_INDEX,\n        _ANALYSIS_ZERO_INDEX,\n        _ZERO_COUNT,\n        _ROOT_ACQUISITION,")
s = once(s, "    summary = {\n        \"schema_version\": 1,", """    observed_verdicts = list(_CLAIM_VERDICTS)
    if _QUALIFICATION_ISSUES:
        observed_verdicts.append(\"INCONCLUSIVE\")
    result_verdict = scientific_verdict(
        observed_verdicts, skipped=_CLAIM_SKIPPED, execution_succeeded=succeeded
    )
    summary = {
        \"schema_version\": 2,
        \"execution_succeeded\": succeeded,
        \"scientific_verdict\": result_verdict,
        \"individual_verdicts\": list(_CLAIM_VERDICTS),
        \"qualification_issues\": list(_QUALIFICATION_ISSUES),
        \"legacy_succeeded_meaning\": \"execution_only_not_scientific_acceptance\",
        \"observable\": \"relative_error_to_indexed_zeta_reference\",
        \"fit_scope\": \"conditional_on_assumed_matching_floor_and_selected_ramp_window\",
        \"source_manifest_binding\": \"not_exposed_by_this_application_schema\",""")
start = s.index("def _run_claim(name, quick):")
end = s.index("def main():", start)
s = s[:start] + """def _run_claim(name, quick):
    global _MEASUREMENTS, _CLAIM_VERDICTS, _CLAIM_SKIPPED, _QUALIFICATION_ISSUES
    _MEASUREMENTS = []
    _CLAIM_VERDICTS = []
    _CLAIM_SKIPPED = False
    _QUALIFICATION_ISSUES = []
    started_at = time.time()
    succeeded = False
    try:
        CLAIMS[name](quick)
        # Failed hypotheses are valuable data: retain/publicize only under
        # the existing explicit publication authorization, not a fabricated PASS.
        _finalize_publication()
        succeeded = True
    finally:
        _write_claim_summary(name, started_at, succeeded)
    observed = list(_CLAIM_VERDICTS)
    if _QUALIFICATION_ISSUES:
        observed.append(\"INCONCLUSIVE\")
    result = scientific_verdict(observed, skipped=_CLAIM_SKIPPED, execution_succeeded=succeeded)
    print(f\"  SCIENTIFIC STATUS: {result}\", flush=True)
    return result in {\"PASS\", \"EXPLORATORY\", \"SKIPPED\"}

""" + s[end:]
s = once(s, """        for name in ALL_ORDER:
            _run_claim(name, args.quick)
        return""", """        accepted = []
        for name in ALL_ORDER:
            accepted.append(_run_claim(name, args.quick))
        if not all(accepted):
            raise SystemExit(1)
        return""")
s = once(s, "    _run_claim(args.claim, args.quick)\n", "    if not _run_claim(args.claim, args.quick):\n        raise SystemExit(1)\n")
path.write_text(s)

# Old ordinal unit fixtures need the newly required converged status; no
# expected measurement value or scientific tolerance is changed.
path = root / "tests/test_reproduce_driver.py"
s = path.read_text()
s = s.replace('{"reference_index":', '{"status": "converged", "reference_index":')
path.write_text(s)
print("materialized strict measurement eligibility, provenance, and scientific verdicts")
