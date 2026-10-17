"""Acceptance thresholds must include their exact boundary, without float loss."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from evaluate import gates


class EvaluationTests(unittest.TestCase):
    def summary(self, before=10, after=8, old_errors=2, new_errors=1):
        return {"v1": {"repeated_errors": old_errors, "median_successful_tool_calls": before,
                       "top3_recall": 1.0, "success_rate": 1.0},
                "v2": {"repeated_errors": new_errors, "median_successful_tool_calls": after,
                       "top3_recall": .9, "success_rate": 1.0}}

    def test_exact_twenty_percent_reduction_passes(self):
        self.assertTrue(gates(self.summary())["release_gate_passed"])
        self.assertTrue(gates(self.summary(before=12.5, after=10))["release_gate_passed"])

    def test_below_twenty_percent_reduction_fails(self):
        self.assertFalse(gates(self.summary(after=8.5))["checks"]["successful_tool_call_reduction"])

    def test_zero_or_absent_baseline_does_not_prove_reduction(self):
        self.assertFalse(gates(self.summary(old_errors=0, new_errors=0))["release_gate_passed"])
        self.assertFalse(gates(self.summary(before=None, after=None))["release_gate_passed"])


if __name__ == "__main__":
    unittest.main()
