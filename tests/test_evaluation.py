from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from evaluate import gates, load_cases, seed, export_legacy


class EvaluationTests(unittest.TestCase):
    def test_scenario_contract(self):
        cases = load_cases()
        self.assertGreaterEqual(len(cases), 20)
        self.assertEqual({"first_failure", "recurrence", "environment_change", "lookalike"}, {c["phase"] for c in cases})
        for case in cases:
            self.assertIsInstance(case["expected_actionable"], bool)
            for field in ("title", "query", "error", "operation", "expected_resolution", "known_bad_action"):
                self.assertTrue(case[field])

    def test_no_claim_when_baseline_is_zero(self):
        baseline = {"repeated_errors": 0, "median_successful_tool_calls": None, "top3_recall": 1, "success_rate": 0}
        result = gates({"v1": baseline, "v2": baseline})
        self.assertFalse(result["release_gate_passed"])
        self.assertIsNone(result["repeat_error_reduction"])
        self.assertIsNone(result["tool_call_reduction"])

    def test_all_four_gates_required(self):
        baseline = {"repeated_errors": 10, "median_successful_tool_calls": 10, "top3_recall": .5, "success_rate": .8}
        improved = {"repeated_errors": 4, "median_successful_tool_calls": 7, "top3_recall": .95, "success_rate": .8}
        self.assertTrue(gates({"v1": baseline, "v2": improved})["release_gate_passed"])
        self.assertFalse(gates({"v1": baseline, "v2": {**improved, "success_rate": .7}})["release_gate_passed"])

    def test_baseline_uses_own_rules_and_preserves_historical_status(self):
        with tempfile.TemporaryDirectory(prefix="wiki-baseline-") as name:
            root = Path(name)
            baseline = root / "v1"
            rules = baseline / "assets/templates/schema/AGENTS.md"
            rules.parent.mkdir(parents=True)
            rules.write_text("# Original rules\nRead existing pages.\nProject key: TODO\n"
                             "Knowledge-base root: TODO\nMaintainer: TODO\n", encoding="utf-8")
            wiki, ids = seed(root / "kb", [c for c in load_cases() if c["id"] == "config-prereq"])
            self.assertEqual(wiki.project_root, root.resolve())
            from llm_wiki.model import serialize
            doc = wiki.find(ids["config-prereq"])
            doc["metadata"].update(status="needs-verification", confidence="observed")
            (wiki.root / doc["path"]).write_text(serialize(doc["metadata"], doc["body"]), encoding="utf-8")
            export_legacy(wiki, baseline)
            self.assertFalse((wiki.root / ".gitignore").exists())
            rendered = (wiki.root / "schema/AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("Read existing pages.", rendered)
            self.assertIn("Project key: evaluation", rendered)
            self.assertIn("Knowledge-base root: " + str(wiki.root), rendered)
            self.assertNotIn("TODO", rendered)
            text = (wiki.root / doc["path"]).read_text(encoding="utf-8")
            self.assertIn("- Status: needs-verification", text)
            self.assertIn("- Confidence: observed", text)


if __name__ == "__main__":
    unittest.main()
