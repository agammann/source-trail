from copy import deepcopy
import json
import unittest
from unittest.mock import Mock

from demo.selector import (CONTEXT_TOKENS, ExtractiveSelector, OUTPUT_TOKENS, PROMPT_BYTE_LIMIT,
                           selection_payload, strict_json)
from sourcetrail.model import ModelError


EVIDENCE = [{"block_id": "P1B1", "text": "The timeout is 12 seconds.", "source_version": "4", "section": "Settings"},
            {"block_id": "P1B2", "text": "The queue holds 9 jobs.", "source_version": "4", "table_header": "Item | Value"}]
RESPONSE = {"done": True, "done_reason": "stop", "model": "fixture-model", "prompt_eval_count": 31, "eval_count": 12,
            "message": {"role": "assistant", "content": '{"block_id":"P1B1"}'}}


class SelectorTests(unittest.TestCase):
    def setUp(self):
        self.runtime = Mock()
        self.request = Mock(return_value=deepcopy(RESPONSE))
        self.selector = ExtractiveSelector(self.runtime, "fixture-model", self.request)

    def answer(self):
        return self.selector.answer("What is the timeout?", EVIDENCE, "4")

    def test_valid_selection_copies_the_passage_and_records_actual_usage(self):
        raw, usage = self.answer()
        self.assertEqual(raw, {"status": "answered", "answer": EVIDENCE[0]["text"],
                               "citations": [{"block_id": "P1B1", "quote": EVIDENCE[0]["text"]}]})
        self.assertEqual((usage["model_calls"], usage["input_tokens"], usage["output_tokens"], usage["usage_recorded"]), (1, 31, 12, True))
        payload = self.request.call_args.args[1]
        self.assertEqual(payload["format"]["properties"]["block_id"]["enum"], ["P1B1", "P1B2", ""])
        self.assertEqual(payload["options"]["num_predict"], OUTPUT_TOKENS)
        self.assertEqual(payload["options"]["num_ctx"], CONTEXT_TOKENS)
        passages = json.loads(payload["messages"][1]["content"])["passages"]
        self.assertEqual(passages, EVIDENCE)
        self.assertNotIn("answer", json.loads(payload["messages"][1]["content"]))

    def test_empty_selection_is_a_valid_abstention_with_one_generation(self):
        self.request.return_value["message"]["content"] = '{"block_id":""}'
        raw, use = self.answer()
        self.assertEqual(raw, {"status": "abstained", "answer": "", "citations": []})
        self.assertEqual(use["model_calls"], 1)

    def test_short_heading_does_not_hide_a_later_valid_top_passage(self):
        evidence = [{"block_id": "P1B0", "text": "AI"}, EVIDENCE[0]]
        raw, use = self.selector.answer("What is the timeout?", evidence)
        self.assertEqual(raw["answer"], EVIDENCE[0]["text"])
        self.assertEqual(self.selector.selection["candidate_block_ids"], ["P1B1"])
        self.assertEqual(use["model_calls"], 1)

    def test_short_factual_passages_still_remain_candidates(self):
        evidence = [{"block_id": "P1B1", "text": "MIT License"},
                    {"block_id": "P1B2", "text": "+1 555 010 0199"},
                    {"block_id": "P1B3", "text": "v4.0"}]
        _, candidates = selection_payload("Which value is shown?", evidence, None, "fixture")
        self.assertEqual(candidates, evidence)

    def test_version_comparison_and_empty_candidates_do_not_generate(self):
        for question, evidence in (("Compare version 3 and version 4", EVIDENCE), ("Question?", []),
                                   ("Question?", [{"block_id": "P1B1", "text": "   "}])):
            with self.subTest(question=question):
                raw, use = self.selector.answer(question, evidence)
                self.assertEqual(raw["status"], "abstained")
                self.assertEqual(use["model_calls"], 0)
        self.request.assert_not_called()
        self.runtime.ensure_ready.assert_not_called()

    def test_unknown_id_and_malformed_or_extra_fields_are_rejected(self):
        for content in ('{"block_id":"not-offered"}', '{"block_id":true}', '{"block_id":null}', '{}', '[]',
                        '{"block_id":"P1B1","answer":"invented"}', '{"block_id":"P1B1","block_id":"P1B2"}',
                        '{"block_id":NaN}', 'not JSON'):
            with self.subTest(content=content):
                self.request.return_value = deepcopy(RESPONSE)
                self.request.return_value["message"]["content"] = content
                with self.assertRaises(ModelError):
                    self.answer()
                self.assertEqual(self.selector.metrics["input_tokens"], 31)

    def test_incomplete_and_invalid_messages_are_not_answers(self):
        for field, values in (("done", (False, 1, None)), ("done_reason", (None, "length", "tool_calls"))):
            for value in values:
                with self.subTest(field=field, value=value):
                    self.request.return_value = deepcopy(RESPONSE)
                    self.request.return_value[field] = value
                    with self.assertRaisesRegex(ModelError, "complete a stopped response"):
                        self.answer()
        for message in (None, {}, {"role": "user", "content": '{"block_id":"P1B1"}'},
                        {"role": "assistant", "content": "x" * 513},
                        {"role": "assistant", "content": '{"block_id":"P1B1"}', "tool_calls": [{"id": "tool"}]}):
            with self.subTest(message=message):
                self.request.return_value = deepcopy(RESPONSE)
                self.request.return_value["message"] = message
                with self.assertRaises(ModelError):
                    self.answer()

    def test_partial_missing_usage_is_unavailable_and_invalid_types_preserve_other_counts(self):
        for value in (None, False, True, "12", 12.0, -1):
            with self.subTest(value=value):
                self.request.return_value = deepcopy(RESPONSE)
                self.request.return_value["eval_count"] = value
                if value is None:
                    _, use = self.answer()
                else:
                    with self.assertRaisesRegex(ModelError, "invalid token usage"):
                        self.answer()
                    use = self.selector.metrics
                self.assertEqual(use["input_tokens"], 31)
                self.assertIsNone(use["output_tokens"])
                self.assertFalse(use["usage_recorded"])
        self.request.return_value = deepcopy(RESPONSE)
        del self.request.return_value["prompt_eval_count"]
        _, use = self.answer()
        self.assertIsNone(use["input_tokens"])
        self.assertEqual(use["output_tokens"], 12)

    def test_excess_usage_is_rejected_without_clipping_the_measured_cost(self):
        for field, value in (("eval_count", 65), ("prompt_eval_count", 4097)):
            with self.subTest(field=field):
                self.request.return_value = deepcopy(RESPONSE)
                self.request.return_value[field] = value
                with self.assertRaisesRegex(ModelError, "token budget"):
                    self.answer()
                measured = "output_tokens" if field == "eval_count" else "input_tokens"
                self.assertEqual(self.selector.metrics[measured], value)

    def test_setup_failure_has_zero_generation_attempts_and_transport_failure_one(self):
        self.runtime.ensure_ready.side_effect = RuntimeError("Setup failed.")
        with self.assertRaises(ModelError):
            self.answer()
        self.assertEqual(self.selector.metrics["model_calls"], 0)
        self.request.assert_not_called()
        self.runtime.ensure_ready.side_effect = None
        self.request.side_effect = OSError("Connection failed.")
        with self.assertRaises(ModelError):
            self.answer()
        self.assertEqual(self.selector.metrics["model_calls"], 1)
        self.assertIsNone(self.selector.metrics["input_tokens"])

    def test_reused_selector_cannot_leak_previous_usage(self):
        self.answer()
        self.request.side_effect = OSError("Connection failed.")
        with self.assertRaises(ModelError):
            self.answer()
        self.assertIsNone(self.selector.metrics["input_tokens"])
        self.assertIsNone(self.selector.metrics["output_tokens"])
        self.assertIsNone(self.selector.selection["selected_block_id"])

    def test_unicode_long_passages_have_a_total_byte_bound_and_exact_prefixes(self):
        evidence = [{"block_id": f"P1B{i}", "text": "文😀" * 1000, "section": "文"} for i in range(5)]
        payload, candidates = selection_payload("Which passage is relevant?", evidence, None, "fixture")
        self.assertLessEqual(len(candidates), 4)
        self.assertGreater(len(candidates), 0)
        serialized = len(json.dumps(payload["messages"], ensure_ascii=False).encode("utf-8")) + len(json.dumps(payload["format"]).encode("utf-8"))
        self.assertLessEqual(serialized, PROMPT_BYTE_LIMIT)
        for passage in candidates:
            self.assertLessEqual(len(passage["text"]), 1200)
            original = next(e["text"] for e in evidence if e["block_id"] == passage["block_id"])
            self.assertTrue(original.startswith(passage["text"]))
        with self.assertRaisesRegex(ModelError, "shorter question"):
            selection_payload("文" * 2000, evidence, None, "fixture")

    def test_strict_outer_json_rejects_duplicate_or_nonfinite_usage(self):
        for raw in ('{"eval_count":1,"eval_count":2}', '{"eval_count":NaN}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                strict_json(raw)


if __name__ == "__main__":
    unittest.main()
