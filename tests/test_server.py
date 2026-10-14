from http.server import ThreadingHTTPServer
import json
from threading import Thread
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

from sourcetrail.server import make_handler


class InspectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler())
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def post(self, body, headers=None):
        req = urllib.request.Request(self.base + "/api/query", data=json.dumps(body).encode(),
                                     headers=headers or {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    def test_empty_inspector_loads_and_health_is_local(self):
        with urllib.request.urlopen(self.base + "/") as response:
            text = response.read().decode()
        self.assertIn("Answers you can trace.", text)
        with urllib.request.urlopen(self.base + "/api/health") as response:
            self.assertEqual(json.loads(response.read())["status"], "ok")

    def test_cross_origin_request_is_rejected(self):
        status, body = self.post({}, {"Content-Type": "application/json", "Origin": "https://outside.example"})
        self.assertEqual(status, 403)

    def test_malformed_input_gets_useful_400(self):
        status, body = self.post({"question": "Question?", "urls": ["https://example.com"], "target_version": [4]})
        self.assertEqual(status, 400)
        self.assertIn("version", body["error"])

    def test_falsy_malformed_versions_are_rejected_instead_of_discarded(self):
        for version in (0, False, [], {}):
            with self.subTest(version=version):
                status, body = self.post({"question": "Question?", "urls": ["https://example.com"], "target_version": version})
                self.assertEqual(status, 400)
                self.assertIn("version", body["error"])

    def test_empty_text_version_is_normalized_and_valid_text_is_preserved(self):
        result = {"status": "abstained", "answer": "", "citations": []}
        for version, expected in (("", None), (None, None), ("v4", "v4")):
            with self.subTest(version=version), patch("sourcetrail.server.query", return_value=result) as query:
                status, _ = self.post({"question": "Question?", "urls": ["https://example.com"], "target_version": version})
                self.assertEqual(status, 200)
                self.assertEqual(query.call_args.args[2], expected)

    def test_non_json_is_rejected(self):
        self.assertEqual(self.post({}, {"Content-Type": "text/plain"})[0], 415)

    def test_result_from_engine_is_returned_unchanged(self):
        evidence_result = {"status": "abstained", "answer": "", "citations": [], "trace": []}
        with patch("sourcetrail.server.query", return_value=evidence_result):
            status, body = self.post({"question": "Question?", "urls": ["https://example.com"]})
        self.assertEqual(status, 200)
        self.assertEqual(body, evidence_result)

    def test_browser_cannot_select_the_provider_model_endpoint_or_authentication(self):
        result = {"status": "abstained", "answer": "", "citations": []}
        with patch("sourcetrail.server.query", return_value=result) as run:
            status, _ = self.post({"question": "Question?", "urls": ["https://example.com"],
                                   "provider": "vllm", "model": "untrusted", "endpoint": "https://outside.example",
                                   "api_key": "untrusted", "allow_local": True})
        self.assertEqual(status, 200)
        self.assertEqual(run.call_args.args, ("Question?", ["https://example.com"], None, "verified", 6, False))
        self.assertEqual(run.call_args.kwargs, {})


if __name__ == "__main__":
    unittest.main()
