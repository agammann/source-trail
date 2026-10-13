"""New synthetic stress-development probes; no inference or external network."""

import unittest
from urllib.parse import urlsplit

from benchmark.holdout.harness import evidence_for, fetch_case, load_cases, serve_fixtures
from benchmark.run import build_command
from sourcetrail.engine import same_version, validate_answer, version_of


class SeparateStressTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = {case["id"]: case for case in load_cases()}
        cls.server = serve_fixtures()
        cls.base = cls.server.__enter__()
        cls.pages = {identifier: fetch_case(case, cls.base) for identifier, case in cls.cases.items()}

    @classmethod
    def tearDownClass(cls):
        cls.server.__exit__(None, None, None)

    def test_six_cases_are_separate_and_explicitly_synthetic(self):
        self.assertEqual(len(self.cases), 6)
        for case in self.cases.values():
            self.assertTrue(case["id"].startswith("h"))
            self.assertIs(case["synthetic"], True)
            self.assertEqual(case["classification"], "stress-development")
            for page in self.pages[case["id"]]:
                self.assertIn("Synthetic stress-development fixture", " ".join(page.blocks))
                self.assertEqual(urlsplit(page.url).hostname, "127.0.0.1")

    def test_long_code_block_is_fetched_in_full(self):
        case = self.cases["h01-late-code-fact"]
        quote = case["required_evidence_quotes"][0]
        block = next(block for page in self.pages[case["id"]] for block in page.blocks if quote in block)
        self.assertGreater(block.index(quote), 3900)

    def test_late_code_fact_survives_evidence_selection(self):
        case = self.cases["h01-late-code-fact"]
        evidence = evidence_for(case, self.pages[case["id"]])
        for quote in case["required_evidence_quotes"]:
            self.assertTrue(any(quote in entry["text"] for entry in evidence), "A fetched fact late in a code block was dropped before inference.")

    def test_numeric_version_40_is_not_version_4(self):
        case = self.cases["h02-numeric-version-suffix"]
        pages = self.pages[case["id"]]
        wrong = next(page for page in pages if page.url.endswith("/v40.html"))
        self.assertFalse(same_version(version_of(wrong), "4"))
        evidence = evidence_for(case, pages)
        self.assertFalse(any(entry["url"] == wrong.url for entry in evidence))

    def test_unseparated_beta_is_not_stable_version_4(self):
        case = self.cases["h03-unseparated-prerelease"]
        pages = self.pages[case["id"]]
        wrong = next(page for page in pages if page.url.endswith("/v4beta.html"))
        self.assertFalse(same_version(version_of(wrong), "4"), "An unseparated prerelease suffix was discarded from the parsed version.")
        evidence = evidence_for(case, pages)
        self.assertFalse(any(entry["url"] == wrong.url for entry in evidence))

    def test_conflicting_statements_on_one_page_can_be_reported(self):
        case = self.cases["h04-same-page-conflict"]
        evidence = evidence_for(case, self.pages[case["id"]])
        proposed = []
        for quote in case["incompatible_quotes"]:
            entry = next(entry for entry in evidence if quote in entry["text"])
            proposed.append({"block_id": entry["block_id"], "quote": quote})
        result = validate_answer({"status": "conflict", "answer": "", "citations": proposed}, evidence)
        self.assertEqual(result["status"], "conflict")
        self.assertEqual(len(result["citations"]), 2)
        self.assertEqual(len({citation["url"] for citation in result["citations"]}), 1)

    def test_operator_table_retains_its_heading_and_column_context(self):
        case = self.cases["h05-multiple-table-context"]
        evidence = evidence_for(case, self.pages[case["id"]])
        row = next(entry for entry in evidence if case["table_quote"] in entry["text"])
        self.assertIn(case["required_table_section"], row["section"], "An incidental short paragraph replaced the table’s actual section heading.")
        self.assertEqual(row["table_header"], case["required_table_header"])

    def test_absent_query_qualifiers_are_not_attested_by_fixture(self):
        case = self.cases["h06-missing-query-qualifiers"]
        all_text = " ".join(block for page in self.pages[case["id"]] for block in page.blocks)
        self.assertIn(case["unqualified_quote"], all_text)
        for qualifier in case["missing_qualifiers"]:
            self.assertNotIn(qualifier.casefold(), all_text.casefold())
        self.assertEqual(case["expected_status"], "abstained")
        self.assertEqual(case["expected_source_paths"], [])

    def test_expected_facts_do_not_enter_application_command(self):
        case = self.cases["h01-late-code-fact"]
        command = build_command(case, self.base, "verified", "ignored-output.json", 6, "unused-model")
        self.assertNotIn(case["expected_answer"], command)
        self.assertNotIn(case["required_evidence_quotes"][0], command)
        self.assertNotIn(case["expected_source_paths"][0], command)


if __name__ == "__main__":
    unittest.main()
