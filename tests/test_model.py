from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Thread
import unittest

from sourcetrail.model import ModelError, Ollama


ANSWER = {"status": "answered", "answer": "12", "citations": [{"block_id": "P1B1", "quote": "The price is 12."}]}
RESPONSE = {
    "done": True,
    "done_reason": "stop",
    "message": {"role": "assistant", "content": json.dumps(ANSWER)},
    "prompt_eval_count": 32,
    "eval_count": 8,
}


class ProviderStub(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_POST(self):
        self.server.requested_path = self.path
        self.server.payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        encoded = json.dumps(self.server.reply).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


class ProviderResponseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), ProviderStub)
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.endpoint = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def answer(self, body):
        self.server.reply = body
        client = Ollama(model="fixture-model", endpoint=self.endpoint, timeout=2)
        return client.answer("What is the price?", [{"block_id": "P1B1", "text": "The price is 12."}])

    def test_complete_reply_records_supplied_usage_and_uses_the_stub(self):
        result, use = self.answer(deepcopy(RESPONSE))
        self.assertEqual(result, ANSWER)
        self.assertEqual(use, {"model_calls": 1, "model": "fixture-model", "input_tokens": 32, "output_tokens": 8, "usage_recorded": True})
        self.assertEqual(self.server.requested_path, "/api/chat")
        self.assertEqual(self.server.payload["model"], "fixture-model")

    def test_missing_usage_is_unavailable_and_preserves_a_known_count(self):
        for absent in [("prompt_eval_count",), ("eval_count",), ("prompt_eval_count", "eval_count")]:
            with self.subTest(absent=absent):
                body = deepcopy(RESPONSE)
                for field in absent:
                    del body[field]
                result, use = self.answer(body)
                self.assertEqual(result, ANSWER)
                self.assertFalse(use["usage_recorded"])
                self.assertEqual(use["input_tokens"], None if "prompt_eval_count" in absent else 32)
                self.assertEqual(use["output_tokens"], None if "eval_count" in absent else 8)

    def test_explicit_zero_counts_are_recorded(self):
        body = deepcopy(RESPONSE)
        body.update(prompt_eval_count=0, eval_count=0)
        _, use = self.answer(body)
        self.assertTrue(use["usage_recorded"])
        self.assertEqual((use["input_tokens"], use["output_tokens"]), (0, 0))

    def test_supplied_invalid_counts_are_rejected(self):
        for field in ("prompt_eval_count", "eval_count"):
            for value in (-1, False, True, 1.5, 1.0, "7", None, [], {}):
                with self.subTest(field=field, value=value):
                    body = deepcopy(RESPONSE)
                    body[field] = value
                    with self.assertRaisesRegex(ModelError, "invalid token count"):
                        self.answer(body)

    def test_false_done_is_an_incomplete_response(self):
        body = deepcopy(RESPONSE)
        body["done"] = False
        with self.assertRaisesRegex(ModelError, "did not complete"):
            self.answer(body)

    def test_non_boolean_and_missing_done_are_rejected(self):
        for value in ("true", "false", 1, 0, None, [], {}):
            with self.subTest(value=value):
                body = deepcopy(RESPONSE)
                body["done"] = value
                with self.assertRaisesRegex(ModelError, "completion flag"):
                    self.answer(body)
        body = deepcopy(RESPONSE)
        del body["done"]
        with self.assertRaisesRegex(ModelError, "completion flag"):
            self.answer(body)

    def test_output_limit_is_not_accepted_as_a_complete_answer(self):
        body = deepcopy(RESPONSE)
        body["done_reason"] = "length"
        with self.assertRaisesRegex(ModelError, "did not complete"):
            self.answer(body)

    def test_missing_optional_completion_reason_is_supported(self):
        body = deepcopy(RESPONSE)
        del body["done_reason"]
        self.assertEqual(self.answer(body)[0], ANSWER)

    def test_malformed_completion_reason_is_rejected(self):
        for value in (None, False, [], {}):
            with self.subTest(value=value):
                body = deepcopy(RESPONSE)
                body["done_reason"] = value
                with self.assertRaisesRegex(ModelError, "completion reason"):
                    self.answer(body)

    def test_malformed_provider_envelope_and_message_fail_cleanly(self):
        for body in ([], None, "body"):
            with self.subTest(body=body), self.assertRaises(ModelError):
                self.answer(body)
        for message in (None, [], "message", {}, {"content": []}, {"content": "not JSON"}):
            with self.subTest(message=message):
                body = deepcopy(RESPONSE)
                body["message"] = message
                with self.assertRaises(ModelError):
                    self.answer(body)


if __name__ == "__main__":
    unittest.main()
