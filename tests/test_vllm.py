from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from threading import Thread
import unittest
from unittest.mock import patch

from sourcetrail.engine import query
from sourcetrail.model import ModelError, Ollama, VLLM, make_model
from sourcetrail.web import Page


ANSWER = {"status": "answered", "answer": "12", "citations": [{"block_id": "P1B1", "quote": "The price is 12."}]}
RESPONSE = {
    "object": "chat.completion",
    "model": "runtime-served-alias",
    "choices": [{"index": 0, "finish_reason": "stop", "message": {
        "role": "assistant", "content": json.dumps(ANSWER), "tool_calls": [], "refusal": None}}],
    "usage": {"prompt_tokens": 32, "completion_tokens": 8, "total_tokens": 40},
}
EVIDENCE = [{"block_id": "P1B1", "text": "The price is 12."}]


class LocalRuntimeStub(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_POST(self):
        self.server.paths.append(self.path)
        self.server.authorization = self.headers.get("Authorization")
        self.server.payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        encoded = self.server.encoded if self.server.encoded is not None else json.dumps(self.server.reply).encode()
        self.send_response(self.server.status)
        if self.server.location:
            self.send_header("Location", self.server.location)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        self.server.paths.append(self.path)
        self.send_response(500)
        self.end_headers()


class VLLMResponseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), LocalRuntimeStub)
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self):
        self.server.reply = deepcopy(RESPONSE)
        self.server.encoded = None
        self.server.status = 200
        self.server.location = None
        self.server.paths = []

    def client(self, **kwargs):
        return VLLM(model="fixture-model", endpoint=self.base, timeout=2, api_key=kwargs.get("api_key", ""))

    def answer(self, body=None):
        if body is not None:
            self.server.reply = body
        return self.client().answer("What is the price?", EVIDENCE, "4")

    def test_complete_reply_uses_structured_json_and_records_runtime_usage(self):
        result, use = self.answer()
        self.assertEqual(result, ANSWER)
        self.assertEqual(use, {"model_calls": 1, "model": "fixture-model", "reported_model": "runtime-served-alias", "input_tokens": 32,
                               "output_tokens": 8, "usage_recorded": True})
        self.assertEqual(self.server.paths, ["/v1/chat/completions"])
        self.assertIsNone(self.server.authorization)
        payload = self.server.payload
        self.assertEqual({k: payload[k] for k in ("model", "stream", "n", "temperature", "max_tokens", "seed")},
                         {"model": "fixture-model", "stream": False, "n": 1, "temperature": 0, "max_tokens": 650, "seed": 7})
        self.assertEqual(payload["response_format"]["type"], "json_schema")
        self.assertTrue(payload["response_format"]["json_schema"]["strict"])
        self.assertEqual(json.loads(payload["messages"][1]["content"])["requested_version"], "4")
        vllm_messages = payload["messages"]
        schema = payload["response_format"]["json_schema"]["schema"]
        self.server.reply = {"done": True, "message": {"content": json.dumps(ANSWER)}}
        Ollama(model="fixture-model", endpoint=self.base, timeout=2).answer("What is the price?", EVIDENCE, "4")
        self.assertEqual(self.server.payload["messages"], vllm_messages)
        self.assertEqual(self.server.payload["format"], schema)

    def test_choice_must_be_unique_index_zero_and_finish_with_stop(self):
        for choices in (None, [], [None], [RESPONSE["choices"][0]] * 2):
            with self.subTest(choices=choices):
                body = deepcopy(RESPONSE)
                body["choices"] = choices
                with self.assertRaises(ModelError):
                    self.answer(body)
        for field, values in (("index", (None, True, 1, "0")),
                              ("finish_reason", (None, "length", "tool_calls", "content_filter", ""))):
            for value in values:
                with self.subTest(field=field, value=value):
                    body = deepcopy(RESPONSE)
                    body["choices"][0][field] = value
                    with self.assertRaisesRegex(ModelError, "complete stopped choice"):
                        self.answer(body)
        body = deepcopy(RESPONSE)
        del body["choices"][0]["finish_reason"]
        with self.assertRaises(ModelError):
            self.answer(body)

    def test_malformed_envelopes_messages_and_structured_content_are_rejected(self):
        for body in ([], "body", {"object": "chat.completion.chunk"}):
            with self.subTest(body=body), self.assertRaises(ModelError):
                self.answer(body)
        for field, values in (("role", (None, "user")), ("content", (None, [], "", "bad json", "[]", "null", '{"answer":NaN}')),
                              ("refusal", ("refused", False)), ("tool_calls", ([{"id": "call"}], False)),
                              ("function_call", ({"name": "tool"},))):
            for value in values:
                with self.subTest(field=field, value=value):
                    body = deepcopy(RESPONSE)
                    body["choices"][0]["message"][field] = value
                    with self.assertRaises(ModelError):
                        self.answer(body)

    def test_supplied_usage_counts_must_be_nonnegative_integers(self):
        for field in ("prompt_tokens", "completion_tokens", "total_tokens"):
            for value in (False, True, -1, 1.5, 1.0, "7", [], {}):
                with self.subTest(field=field, value=value):
                    body = deepcopy(RESPONSE)
                    body["usage"][field] = value
                    with self.assertRaisesRegex(ModelError, "invalid token count"):
                        self.answer(body)
        for value in (False, [], "usage"):
            with self.subTest(usage=value):
                body = deepcopy(RESPONSE)
                body["usage"] = value
                with self.assertRaisesRegex(ModelError, "token usage"):
                    self.answer(body)

    def test_omitted_null_or_partial_usage_keeps_unavailable_counts_explicit(self):
        for missing in (True, False):
            body = deepcopy(RESPONSE)
            if missing:
                del body["usage"]
            else:
                body["usage"] = None
            _, use = self.answer(body)
            self.assertEqual((use["input_tokens"], use["output_tokens"], use["usage_recorded"]), (None, None, False))
        for field in ("prompt_tokens", "completion_tokens"):
            for missing in (True, False):
                body = deepcopy(RESPONSE)
                if missing:
                    del body["usage"][field]
                else:
                    body["usage"][field] = None
                _, use = self.answer(body)
                self.assertFalse(use["usage_recorded"])
                self.assertEqual(use["input_tokens"], None if field == "prompt_tokens" else 32)
                self.assertEqual(use["output_tokens"], None if field == "completion_tokens" else 8)

    def test_reported_model_is_optional_and_separate_from_the_requested_alias(self):
        for missing in (True, False):
            body = deepcopy(RESPONSE)
            if missing:
                del body["model"]
            else:
                body["model"] = None
            _, use = self.answer(body)
            self.assertIsNone(use["reported_model"])
            self.assertEqual(use["model"], "fixture-model")
        for value in (False, [], "", " "):
            with self.subTest(value=value):
                body = deepcopy(RESPONSE)
                body["model"] = value
                with self.assertRaises(ModelError):
                    self.answer(body)

    def test_usage_sum_and_generation_cap_are_checked_and_zero_is_recorded(self):
        for usage in ({"prompt_tokens": 32, "completion_tokens": 8, "total_tokens": 41},
                      {"prompt_tokens": 32, "completion_tokens": 651, "total_tokens": 683},
                      {"completion_tokens": 8, "total_tokens": 1},
                      {"prompt_tokens": 32, "total_tokens": 1}):
            body = deepcopy(RESPONSE)
            body["usage"] = usage
            with self.subTest(usage=usage), self.assertRaisesRegex(ModelError, "inconsistent token usage"):
                self.answer(body)
        body = deepcopy(RESPONSE)
        body["usage"] = dict.fromkeys(("prompt_tokens", "completion_tokens", "total_tokens"), 0)
        _, use = self.answer(body)
        self.assertEqual((use["input_tokens"], use["output_tokens"], use["usage_recorded"]), (0, 0, True))

    def test_read_limit_and_nonfinite_json_fail_cleanly(self):
        for encoded in (b" " * 2_000_001, b'{"object":"chat.completion","usage":NaN}', b"not json"):
            with self.subTest(size=len(encoded)):
                self.server.encoded = encoded
                with self.assertRaises(ModelError):
                    self.answer()

    def test_runtime_authentication_is_only_a_header_and_redirects_are_not_followed(self):
        self.client(api_key="fixture-auth-only").answer("Question?", EVIDENCE)
        self.assertEqual(self.server.authorization, "Bearer fixture-auth-only")
        self.assertNotIn("fixture-auth-only", json.dumps(self.server.payload))
        self.server.paths = []
        self.server.status = 307
        self.server.location = self.base + "/redirected"
        self.server.encoded = b"fixture-auth-only"
        with self.assertRaisesRegex(ModelError, "HTTP 307") as caught:
            self.client(api_key="fixture-auth-only").answer("Question?", EVIDENCE)
        self.assertEqual(self.server.paths, ["/v1/chat/completions"])
        self.assertNotIn("fixture-auth-only", str(caught.exception))

    def test_environment_proxy_is_bypassed_for_local_runtime(self):
        with patch.dict(os.environ, {"HTTP_PROXY": "http://127.0.0.1:1", "HTTPS_PROXY": "http://127.0.0.1:1", "NO_PROXY": ""}):
            self.assertEqual(self.answer()[0], ANSWER)

    def test_engine_factory_keeps_common_exact_quote_and_version_validation(self):
        page = Page("https://docs.example/v4/", "Prices version 4", ["The price is 12."], [], 1, "digest", "text/html", False)
        environment = {"SOURCETRAIL_PROVIDER": "vllm", "SOURCETRAIL_VLLM_URL": self.base,
                       "SOURCETRAIL_MODEL": "fixture-model", "SOURCETRAIL_VLLM_API_KEY": ""}
        with patch.dict(os.environ, environment), patch("sourcetrail.engine.WebReader.fetch", return_value=page):
            valid = query("What is the price?", [page.url], target_version="4", max_pages=1)
            self.assertEqual(valid["status"], "answered")
            self.assertEqual(valid["citations"][0]["source_version"], "4")
            self.assertEqual(valid["metrics"]["input_tokens"], 32)
            body = deepcopy(RESPONSE)
            answer = deepcopy(ANSWER)
            answer["citations"][0]["quote"] = "The invented price is 99."
            body["choices"][0]["message"]["content"] = json.dumps(answer)
            self.server.reply = body
            invalid = query("What is the price?", [page.url], target_version="4", max_pages=1)
            self.assertEqual(invalid["status"], "failed")
            self.assertEqual(invalid["citations"], [])
            with patch("sourcetrail.engine.make_model", side_effect=ModelError("Invalid configuration.")):
                invalid_config = query("What is the price?", [page.url], target_version="4", max_pages=1)
            self.assertEqual(invalid_config["status"], "failed")
            self.assertEqual(invalid_config["metrics"]["model_calls"], 0)


class LocalProviderConfigurationTests(unittest.TestCase):
    def test_vllm_url_must_remain_loopback_without_credentials_or_other_paths(self):
        for endpoint in ("https://api.example/v1", "http://192.168.1.2:8000/v1", "http://0.0.0.0:8000",
                         "http://@127.0.0.1:8000", "http://user:secret@127.0.0.1:8000", "http://127.0.0.1/v1?token=x",
                         "http://127.0.0.1/v1#fragment", "http://127.0.0.1/other", "file:///tmp/runtime",
                         "http://127.0.0.1:0", "http://127.0.0.1:65536", "http://[::1%zone]:8000", "http://127.0.0.1\n:8000"):
            with self.subTest(endpoint=endpoint), self.assertRaises(ModelError):
                VLLM(model="fixture", endpoint=endpoint, api_key="")
        for endpoint, expected in (("http://localhost:8000/", "http://127.0.0.1:8000/v1"),
                                   ("http://127.0.0.1:8000/v1/", "http://127.0.0.1:8000/v1"),
                                   ("http://[::1]:8000", "http://[::1]:8000/v1")):
            self.assertEqual(VLLM(model="fixture", endpoint=endpoint, api_key="").endpoint, expected)

    def test_operator_configuration_rejects_missing_model_bad_timeout_and_invalid_auth(self):
        with patch.dict(os.environ, {}, clear=True):
            for model in (None, "", " ", [], "x" * 257):
                with self.subTest(model=model), self.assertRaises(ModelError):
                    VLLM(model=model)
        for timeout in (False, 0, -1, float("inf"), float("nan"), "2"):
            with self.subTest(timeout=timeout), self.assertRaises(ModelError):
                VLLM(model="fixture", timeout=timeout, api_key="")
        for auth in (False, "contains space", "line\nheader", "nonascii-\u00e9"):
            with self.subTest(auth=auth), self.assertRaises(ModelError):
                VLLM(model="fixture", api_key=auth)

    def test_provider_factory_defaults_to_ollama_and_supports_explicit_or_environment_vllm(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsInstance(make_model(), Ollama)
            self.assertEqual(make_model().model, "qwen3.5:4b-q4_K_M")
        with patch.dict(os.environ, {"SOURCETRAIL_PROVIDER": "vllm", "SOURCETRAIL_MODEL": "fixture",
                                     "SOURCETRAIL_VLLM_URL": "http://127.0.0.1:8000/v1", "SOURCETRAIL_VLLM_API_KEY": ""}):
            self.assertIsInstance(make_model(), VLLM)
            self.assertEqual(make_model(model="override").model, "override")
            self.assertIsInstance(make_model(provider="ollama"), Ollama)
        for provider in ("", "external", [], True):
            with self.subTest(provider=provider), self.assertRaises(ModelError):
                make_model(provider=provider)

    def test_cli_uses_operator_selected_factory(self):
        from sourcetrail.__main__ import main
        class Capture(io.StringIO):
            def reconfigure(self, **_):
                pass
        result = {"status": "abstained", "answer": "", "citations": []}
        client = object()
        argv = ["sourcetrail", "query", "--question", "Question?", "--url", "https://example.com",
                "--provider", "vllm", "--model", "fixture"]
        with patch("sys.argv", argv), patch("sys.stdout", new=Capture()), patch(
                "sourcetrail.__main__.make_model", return_value=client) as factory, patch(
                "sourcetrail.__main__.query", return_value=result) as run:
            self.assertEqual(main(), 0)
        factory.assert_called_once_with(model="fixture", provider="vllm")
        self.assertIs(run.call_args.args[6], client)


if __name__ == "__main__":
    unittest.main()
