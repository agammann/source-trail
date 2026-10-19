import time
import unittest
from unittest.mock import patch

from sourcetrail.engine import is_version_comparison, query, same_version, select_evidence, validate_answer, version_of
from sourcetrail.model import ModelError
from sourcetrail.web import Page, WebReadError


def page(url, title, blocks):
    return Page(url, title, blocks, [], 1, "digest", "text/html", False)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.pages = [page("https://docs.example/v2/", "Aster version 2", ["Default cache is route_cache."]),
                      page("https://docs.example/v3/", "Aster version 3", ["Default cache is page_cache."])]

    def test_wrong_version_filtered(self):
        evidence = select_evidence(self.pages, "What is the cache option?", "3")
        self.assertEqual({e["url"] for e in evidence}, {self.pages[1].url})

    def test_single_version_change_is_not_cross_version_comparison(self):
        self.assertFalse(is_version_comparison("How do I change cache settings in version 3?"))
        self.assertFalse(is_version_comparison("What is the cache in the old version?"))
        self.assertTrue(is_version_comparison("How did cache change from version 2 to version 3?"))
        self.assertTrue(is_version_comparison("How does this compare with the previous version?"))
        self.assertTrue(is_version_comparison("Compare v4.0-rc.1 and v4.0"))

    def test_prerelease_comparison_keeps_and_requires_both_versions(self):
        pages = [page("https://example.com/v4.0-rc.1/", "Settings", ["Timeout is 7 seconds."]),
                 page("https://example.com/v4.0/", "Settings", ["Timeout is 9 seconds."])]
        evidence = select_evidence(pages, "Compare v4.0-rc.1 and v4.0", "4.0")
        self.assertEqual({e["source_version"] for e in evidence}, {"4.0-rc.1", "4.0"})
        raw = {"status": "answered", "answer": "7 to 9 seconds", "citations": [{"block_id": e["block_id"], "quote": e["text"]} for e in evidence]}
        self.assertEqual(validate_answer(raw, evidence, "4.0", comparison=True, comparison_versions=["4.0-rc.1", "4.0"])["status"], "answered")

    def test_query_requires_every_explicit_comparison_version(self):
        pages = [page(f"https://example.com/v{v}/", "Settings", [f"The timeout in version {v} is 9 seconds."]) for v in ("4.0-rc.1", "4.0", "3.9")]
        class IncompleteModel:
            def answer(self, question, evidence, target_version):
                return {"status": "answered", "answer": "9 seconds", "citations": [{"block_id": e["block_id"], "quote": e["text"]} for e in evidence if e["source_version"] != "4.0-rc.1"]}, {"input_tokens": 1, "output_tokens": 1}
        with patch("sourcetrail.engine.WebReader.fetch", side_effect=pages):
            result = query("Compare v4.0-rc.1 and v4.0", [p.url for p in pages], target_version="4.0", max_pages=3, model=IncompleteModel())
        self.assertEqual(result["status"], "failed")
        self.assertIn("every requested version", result["error"])

    def test_adjacent_tables_do_not_inherit_another_currency_header(self):
        p = Page("https://example.com/prices", "Prices", ["Item | USD", "Basic | 12", "Item | EUR", "Basic | 20"], [], 1, "digest", "text/html", False, ["tr"] * 4, [1, 1, 2, 2])
        evidence = select_evidence([p], "What is the Basic price in EUR?")
        row = next(e for e in evidence if e["text"] == "Basic | 20")
        self.assertEqual(row["table_header"], "Item | EUR")

    def test_prerelease_marker_is_preserved_and_cannot_match_stable_major(self):
        for marker in ("4beta", "4.0-rc.1", "4.0-dev", "4.0-preview.2", "40"):
            with self.subTest(marker=marker):
                actual = version_of(page(f"https://example.com/v{marker}/", "Documentation", []))
                self.assertEqual(actual, marker)
                self.assertFalse(same_version(actual, "4"))
        self.assertTrue(same_version("4.0-rc.1", "4.0-rc.1"))

    def test_version_marker_accepts_existing_spelling_and_spacing(self):
        for marker, expected in (("version4", "4"), ("version 4", "4"),
                                 ("version:4", "4"), ("version : 4", "4"),
                                 ("release 4", "4"), ("release:\t4.0", "4.0"),
                                 ("v4.0-rc.1", "4.0-rc.1")):
            with self.subTest(marker=marker):
                self.assertEqual(version_of(page("https://example.com/docs", marker, [])), expected)

    def test_unmatched_version_prefix_in_page_text_is_bounded(self):
        # A public page may put a long run of whitespace after either prefix.
        # The version matcher must not retry all splits between two whitespace runs.
        hostile_title = "version" + " " * 16000 + "x"
        hostile_block = "release" + "\t" * 16000 + "x"
        started = time.monotonic()
        self.assertIsNone(version_of(page("https://example.com/docs", hostile_title, [hostile_block])))
        self.assertLess(time.monotonic() - started, 1.0)

    def test_query_relevant_late_passage_is_available_without_cutting_quote(self):
        fact = "The aurora cache expiration is 19 seconds."
        block = "Boilerplate padding. " * 300 + fact
        evidence = select_evidence([page("https://example.com", "Settings", [block])], "What is the aurora cache expiration?")
        self.assertTrue(any(fact in e["text"] for e in evidence))
        self.assertIn(fact, evidence[0]["text"])
        result = validate_answer({"status": "answered", "answer": "19 seconds", "citations": [{"block_id": evidence[0]["block_id"], "quote": fact}]}, evidence)
        self.assertEqual(result["status"], "answered")

    def test_table_context_uses_heading_tags_and_preserves_empty_first_cell(self):
        p = page("https://example.com", "Prices", ["North campus", "Prices exclude tax.", "Plan | Price", "| 12 dollars", "South campus", "Plan | Price", "Basic | 20 dollars"])
        p = Page(p.url, p.title, p.blocks, [], 1, "digest", "text/html", False, ["h2", "p", "tr", "tr", "h2", "tr", "tr"])
        evidence = select_evidence([p], "What is the North campus price?")
        row = next(e for e in evidence if e["text"] == "| 12 dollars")
        self.assertEqual(row["table_header"], "Plan | Price")
        self.assertEqual(row["section"], "North campus")
        row = next(e for e in evidence if e["text"] == "Basic | 20 dollars")
        self.assertEqual(row["section"], "South campus")

    def test_two_incompatible_passages_on_one_page_can_be_reported(self):
        evidence = select_evidence([page("https://example.com", "Policy", ["Returns are accepted for 10 days.", "Returns are accepted for 20 days."])], "What is the return period?")
        result = validate_answer({"status": "conflict", "answer": "", "citations": [{"block_id": e["block_id"], "quote": e["text"]} for e in evidence]}, evidence)
        self.assertEqual(result["status"], "conflict")

    def test_version_comparison_requires_both_versions_in_citations(self):
        evidence = select_evidence(self.pages, "Compare version 2 and version 3", "3")
        raw = {"status": "answered", "answer": "route_cache to page_cache", "citations": [{"block_id": "P2B1", "quote": "Default cache is page_cache."}]}
        with self.assertRaises(ModelError):
            validate_answer(raw, evidence, "3", comparison=True)
        raw["citations"].append({"block_id": "P1B1", "quote": "Default cache is route_cache."})
        self.assertEqual(validate_answer(raw, evidence, "3", comparison=True)["status"], "answered")

    def test_missing_model_usage_stays_unavailable(self):
        class PartialUsageModel:
            def answer(self, *_):
                return {"status": "abstained", "answer": "", "citations": []}, {"input_tokens": 40, "output_tokens": None, "usage_recorded": False}
        with patch("sourcetrail.engine.WebReader.fetch", return_value=self.pages[1]):
            result = query("Question?", ["https://docs.example/v3/"], model=PartialUsageModel())
        self.assertFalse(result["metrics"]["usage_recorded"])
        self.assertIsNone(result["metrics"]["output_tokens"])

    def test_requested_version_requires_identifiable_matching_context(self):
        unknown = page("https://example.com/current", "Generic settings", ["The value is 42."])
        self.assertEqual(select_evidence([unknown], "What is the value in version 4?", "4"), [])

    def test_explicit_archives_are_excluded_only_for_current_requests(self):
        old = page("https://example.com/2024", "Warranty policy — archived", ["Warranty is 30 days."])
        new = page("https://example.com/2026", "Current warranty policy", ["Warranty is 90 days."])
        evidence = select_evidence([old, new], "What is the current warranty?")
        self.assertEqual({e["url"] for e in evidence}, {new.url})
        self.assertEqual(len({e["url"] for e in select_evidence([old, new], "What was the warranty in 2024?")}), 2)

    def test_malformed_response_types_fail_closed(self):
        with self.assertRaises(ModelError):
            validate_answer({"status": [], "answer": "", "citations": []}, [])
        with self.assertRaises(ModelError):
            validate_answer({"status": "answered", "answer": "x", "citations": [{"block_id": [], "quote": "text"}]}, [])

    def test_failed_acquisition_is_not_a_considered_abstention(self):
        with patch("sourcetrail.engine.WebReader.fetch", side_effect=WebReadError("Read failed.")):
            result = query("What is the value?", ["https://example.com"])
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["metrics"]["model_calls"], 0)

    def test_failed_model_attempt_is_recorded(self):
        class FailedModel:
            def answer(self, *_):
                raise ModelError("Invalid response.")
        with patch("sourcetrail.engine.WebReader.fetch", return_value=self.pages[1]):
            result = query("What is the value?", ["https://docs.example/v3/"], model=FailedModel())
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["metrics"]["model_calls"], 1)
        self.assertFalse(result["metrics"]["usage_recorded"])

    def test_comparison_preserves_old_source(self):
        evidence = select_evidence(self.pages, "How did the cache change from version 2 to version 3?", "3")
        self.assertEqual(len({e["url"] for e in evidence}), 2)

    def test_baseline_keeps_versions(self):
        self.assertEqual(len({e["url"] for e in select_evidence(self.pages, "cache?", "3", "baseline")}), 2)

    def test_version_does_not_read_arbitrary_numbers(self):
        self.assertIsNone(version_of(page("https://example.com/open", "Hours 09:00", ["Tickets cost 12 dollars."])))
        self.assertFalse(same_version("4-beta", "4"))
        self.assertTrue(same_version("4.2", "4"))

    def test_url_version_wins_over_title_mentions(self):
        self.assertEqual(version_of(page("https://example.com/v2/", "Migration to version 3", [])), "2")

    def test_serialized_evidence_metadata_is_within_cap(self):
        import json
        evidence = select_evidence([page("https://example.com/" + "x" * 2000, "T" * 1000,
                                        ["value " * 100] * 40)], "value")
        self.assertLessEqual(sum(len(json.dumps(e, ensure_ascii=False).encode()) for e in evidence), 12000)

    def test_invented_citation_rejected(self):
        evidence = select_evidence(self.pages, "cache", "3")
        with self.assertRaises(ModelError):
            validate_answer({"status": "answered", "answer": "page_cache", "citations": [{"block_id": "P2B1", "quote": "invented claim"}]}, evidence)

    def test_citation_bound_to_exact_block(self):
        evidence = select_evidence(self.pages, "cache", "3")
        result = validate_answer({"status": "answered", "answer": "page_cache", "citations": [{"block_id": "P2B1", "quote": "Default cache is page_cache."}]}, evidence, "3")
        self.assertEqual(result["citations"][0]["url"], self.pages[1].url)

    def test_repeated_exact_citations_are_validated_then_deduplicated(self):
        evidence = select_evidence(self.pages, "cache")
        proposed = [{"block_id": e["block_id"], "quote": e["text"]} for e in evidence] * 6
        result = validate_answer({"status": "answered", "answer": "page_cache", "citations": proposed}, evidence)
        self.assertEqual(len(result["citations"]), 2)
        proposed.append({"block_id": evidence[0]["block_id"], "quote": "invented claim"})
        with self.assertRaises(ModelError):
            validate_answer({"status": "answered", "answer": "page_cache", "citations": proposed}, evidence)

    def test_distinct_citation_limit_still_applies_after_deduplication(self):
        evidence = select_evidence([page("https://example.com", "Facts", [f"Value number {i} is recorded." for i in range(11)])], "Value")
        with self.assertRaises(ModelError):
            validate_answer({"status": "answered", "answer": "values", "citations": [{"block_id": e["block_id"], "quote": e["text"]} for e in evidence]}, evidence)

    def test_raw_citation_list_remains_bounded_even_with_duplicates(self):
        evidence = select_evidence(self.pages, "cache", "3")
        with self.assertRaises(ModelError):
            validate_answer({"status": "answered", "answer": "page_cache", "citations": [{"block_id": "P2B1", "quote": "Default cache is page_cache."}] * 65}, evidence)

    def test_conflict_requires_two_sources(self):
        with self.assertRaises(ModelError):
            validate_answer({"status": "conflict", "answer": "", "citations": [{"block_id": "P2B1", "quote": "Default cache is page_cache."}]}, select_evidence(self.pages, "cache"))

    def test_abstention_requires_empty_fields(self):
        with self.assertRaises(ModelError):
            validate_answer({"status": "abstained", "answer": "unknown", "citations": []}, [])


if __name__ == "__main__":
    unittest.main()
