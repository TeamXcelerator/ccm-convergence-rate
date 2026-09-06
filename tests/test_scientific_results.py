"""Synthetic driver tests; no numerical runs, credentials, or remote artifacts."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
import io
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import scientific_results as results
SPEC = importlib.util.spec_from_file_location("audit_reproduce", ROOT / "scripts/reproduce.py")
reproduce = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reproduce)


class ScientificResultsTests(unittest.TestCase):
    def test_only_converged_finite_measurements_enter_fits(self):
        for status in ["stagnated", "approximate", "failed", "missing"]:
            self.assertIsNone(results.qualified_digits({"status": status, "matching_digits_f64": 999.0}))
        for value in [float("nan"), float("inf"), None, True, "100"]:
            self.assertIsNone(results.qualified_digits({"status": "converged", "matching_digits_f64": value}))
        self.assertEqual(results.qualified_digits({"status": "converged", "matching_digits_f64": -1.0}), -1.0)

    def test_failed_verdict_is_not_successful_execution(self):
        self.assertEqual(results.scientific_verdict(["FAIL"], skipped=False, execution_succeeded=True), "FAIL")
        self.assertEqual(results.scientific_verdict([], skipped=False, execution_succeeded=True), "INCONCLUSIVE")
        self.assertEqual(results.scientific_verdict([], skipped=True, execution_succeeded=True), "SKIPPED")
        self.assertEqual(results.scientific_verdict(["PASS"], skipped=False, execution_succeeded=False), "EXECUTION_FAILED")
        self.assertEqual(results.scientific_verdict(["PASS", "INCONCLUSIVE"], skipped=False, execution_succeeded=True), "INCONCLUSIVE")

    def test_root_window_rejects_missing_duplicate_and_unknown_status(self):
        good = {"zero_count_returned": 2, "roots": [{"reference_index": 3, "status": "converged"}, {"reference_index": 4, "status": "stagnated"}]}
        results.validate_root_window(good, 3, 2)
        for bad in [
            {"zero_count_returned": 1, "roots": good["roots"]},
            {"zero_count_returned": 2, "roots": [good["roots"][0]] * 2},
            {"zero_count_returned": 2, "roots": [{"reference_index": 3, "status": "invented"}, good["roots"][1]]},
        ]:
            with self.assertRaises(ValueError):
                results.validate_root_window(bad, 3, 2)

    def test_receipt_rejects_changed_output_binary_and_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ["Cargo.toml", "Cargo.lock", "src/main.rs", "scripts/reproduce.py", "scripts/scientific_results.py", "binary"]:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("synthetic fixture " + name)
            report = root / "measurement.json"
            report.write_text(json.dumps({"reference_dataset": {"content_sha256": "a" * 64}}))
            results.stamp_measurement(str(report), "binary", str(root))
            results.verify_measurement_provenance(str(report), "binary", str(root))
            original = report.read_text()
            report.write_text(original + " ")
            with self.assertRaises(ValueError):
                results.verify_measurement_provenance(str(report), "binary", str(root))
            report.write_text(original)
            (root / "binary").write_text("different executable")
            with self.assertRaises(ValueError):
                results.verify_measurement_provenance(str(report), "binary", str(root))
            results.stamp_measurement(str(report), "binary", str(root))
            (root / "Cargo.lock").write_text("different dependency lockfile")
            with self.assertRaises(ValueError):
                results.verify_measurement_provenance(str(report), "binary", str(root))

    def test_legacy_measurement_without_receipt_is_not_resumed(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "measurement.json"
            path.write_text("{}")
            with self.assertRaises(OSError):
                results.verify_measurement_provenance(str(path), "unused", temporary)

    def test_run_claim_records_fail_and_returns_failure(self):
        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(reproduce, "_RESULTS_DIR", temporary), mock.patch.object(reproduce, "_ANALYSIS_ZERO_INDEX", 1), mock.patch.object(reproduce, "_finalize_publication"), mock.patch.dict(reproduce.CLAIMS, {"synthetic": lambda quick: reproduce.verdict(False)}), redirect_stdout(io.StringIO()):
            self.assertFalse(reproduce._run_claim("synthetic", False))
            reports = list((Path(temporary) / "claims").glob("*.json"))
            self.assertEqual(len(reports), 1)
            report = json.loads(reports[0].read_text())
            self.assertTrue(report["execution_succeeded"])
            self.assertEqual(report["scientific_verdict"], "FAIL")

    def test_unresolved_selected_root_marks_claim_inconclusive(self):
        with mock.patch.object(reproduce, "_ANALYSIS_ZERO_INDEX", 1), mock.patch.object(reproduce, "_QUALIFICATION_ISSUES", []):
            digits = reproduce._selected_digits({"roots": [{"reference_index": 1, "status": "stagnated", "matching_digits_f64": 800.0}]})
            self.assertIsNone(digits)
            self.assertTrue(reproduce._QUALIFICATION_ISSUES)

    def test_degenerate_fit_is_inconclusive_instead_of_dividing_by_zero(self):
        with mock.patch.object(reproduce, "_QUALIFICATION_ISSUES", []):
            reproduce.linfit([], [])
            reproduce.linfit([1, 1], [2, 3])
            self.assertEqual(len(reproduce._QUALIFICATION_ISSUES), 2)


if __name__ == "__main__":
    unittest.main()
