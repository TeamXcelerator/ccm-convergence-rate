"""Unit tests for the non-numerical reproduction-driver behavior."""

import importlib.util
import pathlib
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "reproduce", REPO_ROOT / "scripts" / "reproduce.py"
)
reproduce = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(reproduce)


class MultiZeroDriverTests(unittest.TestCase):
    def setUp(self):
        self.original = (
            reproduce._FIRST_ZERO_INDEX,
            reproduce._ZERO_COUNT,
            reproduce._ANALYSIS_ZERO_INDEX,
            reproduce._NUMERICAL_PROFILE,
        )

    def tearDown(self):
        (
            reproduce._FIRST_ZERO_INDEX,
            reproduce._ZERO_COUNT,
            reproduce._ANALYSIS_ZERO_INDEX,
            reproduce._NUMERICAL_PROFILE,
        ) = self.original

    def test_selected_digits_uses_requested_ordinal(self):
        reproduce._ANALYSIS_ZERO_INDEX = 7
        report = {
            "roots": [
                {"reference_index": 6, "matching_digits_f64": 12.5},
                {"reference_index": 7, "matching_digits_f64": 9.25},
            ]
        }
        self.assertEqual(reproduce._selected_digits(report), 9.25)

    def test_missing_ordinal_is_an_unresolved_point(self):
        reproduce._ANALYSIS_ZERO_INDEX = 5
        report = {
            "roots": [
                {"reference_index": 1, "matching_digits_f64": 10.0},
                {"reference_index": 2, "matching_digits_f64": 8.0},
            ]
        }
        self.assertIsNone(reproduce._selected_digits(report))

    def test_measurement_identity_contains_window_and_profile(self):
        reproduce._FIRST_ZERO_INDEX = 21
        reproduce._NUMERICAL_PROFILE = "current"
        path = reproduce._measurement_path(50, 400, 700, 10)
        self.assertTrue(path.endswith("l2-50-n-400-p-700-z-21-10-current.json"))

    def test_higher_ordinal_verdict_is_exploratory(self):
        reproduce._ANALYSIS_ZERO_INDEX = 2
        self.assertEqual(reproduce.verdict(True), "EXPLORATORY")
        self.assertEqual(reproduce.verdict(False), "EXPLORATORY")


if __name__ == "__main__":
    unittest.main()
