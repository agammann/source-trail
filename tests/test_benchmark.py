"""Evaluator checks that never invoke a model or external network."""

import json
from pathlib import Path
import tempfile
import unittest
from urllib.request import urlopen

from benchmark.run import HERE, answer_matches, build_command, fixture_server, score_case, visible_text


class BenchmarkEvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "answer.html").write_text("<html><head><title>Hidden answer</title></head><body><p>The maximum is 12 workers.</p><p>Fish &amp; chips.</p></body></html>", encoding="utf-8")
        self.base = "http://127.0.0.1:12345/"
        self.case = {"id": "test", "expected_status": "answered", "expected_answer": "12 workers", "expected_source_paths": ["/answer.html"]}
        self.result = {
            "answer": "12 workers", "status": "answered",
            "citations": [{"url": self.base + "answer.html", "quote": "The maximum is 12 workers.", "block_id": "p1", "source_version": None}],
            "metrics": {"pages": 2, "model_calls": 1, "input_tokens": 200, "output_tokens": 20, "duration_ms": 10}, "trace": [],
        }

    def tearDown(self):
        self.temp.cleanup()

    def score(self):
        return score_case(self.case, self.result, self.base, self.root)

    def test_valid_supported_answer_passes(self):
        self.assertTrue(self.score()["passed"])

    def test_answer_aliases_require_full_tokens_and_reject_negation(self):
        self.assertTrue(answer_matches("12 workers.", ["12 workers"]))
        self.assertFalse(answer_matches("It permits 12 workers.", ["12 workers"]))
        self.assertFalse(answer_matches("It permits 112 workers.", ["12 workers"]))
        self.assertFalse(answer_matches("The option is not disabled.", ["disabled"]))
        self.assertFalse(answer_matches("Use enabled instead of disabled.", ["disabled"]))

    def test_mixed_correct_and_wrong_answer_is_not_correct(self):
        self.assertTrue(answer_matches("Adaptive", ["adaptive"]))
        self.assertFalse(answer_matches("adaptive or linear", ["adaptive"]))
        self.assertFalse(answer_matches("adaptive, but linear is also possible", ["adaptive"]))

    def test_wrong_or_missing_units_require_an_explicit_alias(self):
        self.assertFalse(answer_matches("8 minutes", ["8 seconds"]))
        self.assertFalse(answer_matches("8", ["8 seconds"]))
        self.assertTrue(answer_matches("8", ["8 seconds", "8"]))
        self.assertTrue(answer_matches("eight seconds", ["8 seconds", "eight seconds"]))

    def test_development_case_01_alias_preserves_one_default_policy(self):
        cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
        case = next(case for case in cases if case["id"] == "01-doc-old-distractor")
        aliases = [case["expected_answer"], *case["answer_aliases"]]
        self.assertTrue(answer_matches("adaptive retry policy", aliases))
        self.assertFalse(answer_matches("adaptive or fixed retry policy", aliases))
        self.assertFalse(answer_matches("fixed retry policy", aliases))

    def test_development_case_07_alias_preserves_values_versions_and_units(self):
        cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
        case = next(case for case in cases if case["id"] == "07-doc-cross-version-comparison")
        aliases = [case["expected_answer"], *case["answer_aliases"]]
        correct = "The per-client request quota increased from 40 requests per minute in version 2 to 80 requests per minute in version 3."
        self.assertTrue(answer_matches(correct, aliases))
        self.assertFalse(answer_matches(correct.replace("per minute", "per second"), aliases))
        self.assertFalse(answer_matches(correct.replace("40 requests", "80 requests", 1), aliases))
        self.assertFalse(answer_matches(correct.replace("version 2", "version 3", 1), aliases))
        self.assertFalse(answer_matches(correct + " Or it remained unchanged.", aliases))

    def test_failed_status_is_not_rescued_by_a_correct_answer_alias(self):
        self.result["status"] = "failed"
        score = self.score()
        self.assertTrue(score["answer_match"])
        self.assertFalse(score["status_match"])
        self.assertFalse(score["passed"])

    def test_wrong_status_cannot_pass_on_answer_text(self):
        self.result["status"] = "conflict"
        self.assertFalse(self.score()["passed"])

    def test_fabricated_quote_is_rejected(self):
        self.result["citations"][0]["quote"] = "The maximum is 15 workers."
        self.assertFalse(self.score()["valid_quotes"])

    def test_hidden_metadata_is_not_valid_evidence(self):
        self.result["citations"][0]["quote"] = "Hidden answer"
        self.assertFalse(self.score()["valid_quotes"])

    def test_quote_whitespace_and_html_entities_are_normalized(self):
        self.result["citations"][0]["quote"] = "Fish  &\nchips."
        self.assertTrue(self.score()["valid_quotes"])

    def test_hidden_descendants_do_not_become_quote_evidence(self):
        (self.root / "answer.html").write_text('<div hidden><div>Invisible claim.</div>Also invisible.</div><p>Visible claim.</p>', encoding="utf-8")
        text = visible_text(self.root / "answer.html")
        self.assertEqual(text, "Visible claim.")

    def test_table_quote_uses_visible_row_separators(self):
        (self.root / "answer.html").write_text("<table><tr><td>Books</td><td>$18</td></tr></table>", encoding="utf-8")
        self.result["citations"][0]["quote"] = "Books | $18"
        self.assertTrue(self.score()["valid_quotes"])

    def test_extra_unnecessary_source_fails_exact_set(self):
        (self.root / "extra.html").write_text("<p>Other information.</p>", encoding="utf-8")
        self.result["citations"].append({"url": self.base + "extra.html", "quote": "Other information.", "block_id": "p1", "source_version": None})
        self.assertFalse(self.score()["source_match"])

    def test_external_origin_cannot_impersonate_fixture(self):
        self.result["citations"][0]["url"] = "https://example.invalid/answer.html"
        score = self.score()
        self.assertFalse(score["source_match"])
        self.assertFalse(score["valid_quotes"])

    def test_abstention_requires_no_supporting_source(self):
        self.case.update({"expected_status": "abstained", "expected_answer": "", "expected_source_paths": []})
        self.result.update({"status": "abstained", "answer": "No supporting information found.", "citations": []})
        self.assertTrue(self.score()["passed"])

    def test_page_budget_is_enforced(self):
        self.result["metrics"]["pages"] = 7
        self.assertFalse(self.score()["page_budget_met"])

    def test_nonfinite_or_boolean_metrics_are_rejected(self):
        self.result["metrics"]["pages"] = True
        self.result["metrics"]["duration_ms"] = float("nan")
        self.assertFalse(self.score()["passed"])

    def test_runner_command_does_not_send_ground_truth(self):
        case = {**self.case, "question": "What is the maximum?", "start_path": "/index.html", "target_version": "4", "expected_answer": "SECRET EXPECTED PHRASE"}
        command = build_command(case, self.base, "verified", self.root / "output.json", 6, "qwen3.5:4b-q4_K_M")
        self.assertNotIn("SECRET EXPECTED PHRASE", command)
        self.assertNotIn("/answer.html", command)
        self.assertIn("--allow-local", command)
        self.assertEqual(command[command.index("--target-version") + 1], "4")

    def test_fixture_server_serves_only_fictional_pages(self):
        with fixture_server(self.root) as base:
            with urlopen(base + "answer.html", timeout=5) as response:
                self.assertIn("12 workers", response.read().decode("utf-8"))

    def test_all_16_cases_are_synthetic_and_have_existing_sources(self):
        cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
        self.assertEqual(len(cases), 16)
        self.assertEqual(len({case["id"] for case in cases}), 16)
        for case in cases:
            self.assertIs(case["synthetic"], True)
            self.assertIn("Synthetic benchmark fixture", visible_text(HERE / "fixtures" / case["start_path"].lstrip("/")))
            for source in case["expected_source_paths"]:
                self.assertTrue((HERE / "fixtures" / source.lstrip("/")).is_file(), source)


if __name__ == "__main__":
    unittest.main()
