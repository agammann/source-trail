from copy import deepcopy
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from demo.bootstrap import (ARCHIVE_SHA256, DemoBusy, DemoRuntime, ENDPOINT, MODEL,
                            MODEL_DIGEST, RuntimeUnavailable, _api, _extract_tar, _install_binary)
from sourcetrail.engine import validate_answer
from sourcetrail.web import Page


class DemoRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.runtime = DemoRuntime()

    def tearDown(self):
        self.runtime.close()

    def test_busy_query_does_not_start_another_engine_or_runtime(self):
        self.runtime.lock.acquire()
        try:
            with patch("demo.bootstrap.query") as run, self.assertRaises(DemoBusy):
                self.runtime.run_query("Question?", ["https://example.com"])
            run.assert_not_called()
        finally:
            self.runtime.lock.release()

    def test_public_query_uses_fixed_core_controls_and_releases_lock(self):
        result = {"status": "abstained", "answer": "", "citations": [], "metrics": {}}
        with patch("demo.bootstrap.query", return_value=deepcopy(result)) as run:
            actual = self.runtime.run_query("Question?", ["https://example.com"], "4")
        self.assertEqual(run.call_args.args, ("Question?", ["https://example.com"]))
        self.assertEqual({k: v for k, v in run.call_args.kwargs.items() if k != "model"},
                         {"target_version": "4", "mode": "verified", "max_pages": 3, "allow_local": False})
        self.assertEqual(actual["demo_runtime"]["model"], MODEL)
        self.assertEqual(actual["demo_runtime"]["model_digest"], MODEL_DIGEST)
        self.assertFalse(self.runtime.lock.locked())
        with patch("demo.bootstrap.query", side_effect=ValueError("Invalid input.")), self.assertRaises(ValueError):
            self.runtime.run_query("Question?", [])
        self.assertFalse(self.runtime.lock.locked())

    def test_private_source_is_blocked_without_starting_the_model(self):
        with patch.object(self.runtime, "ensure_ready") as prepare:
            result = self.runtime.run_query("Question?", ["http://127.0.0.1:1/private"])
        prepare.assert_not_called()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["metrics"]["model_calls"], 0)

    def test_actual_engine_keeps_exact_quote_validation(self):
        page = Page("https://docs.example/v4/", "Settings version 4", ["The timeout is 12 seconds."], [],
                    1, "digest", "text/html", False)
        response = {"done": True, "done_reason": "stop", "message": {"role": "assistant", "content": '{"block_id":"P1B1"}'},
                    "prompt_eval_count": 10, "eval_count": 8}
        with patch("sourcetrail.engine.WebReader.fetch", return_value=page), patch.object(
                self.runtime, "ensure_ready"), patch("demo.bootstrap._api", return_value=response) as client, patch(
                "sourcetrail.engine.validate_answer", wraps=validate_answer) as validator:
            result = self.runtime.run_query("What is the timeout?", [page.url], "4")
            self.assertEqual(result["status"], "answered")
            self.assertEqual(result["answer"], page.blocks[0])
            self.assertEqual(result["citations"][0]["quote"], page.blocks[0])
            self.assertEqual(result["citations"][0]["source_version"], "4")
            validator.assert_called_once()
            self.assertEqual(client.call_args.args[0], "/api/chat")
            response["message"]["content"] = '{"block_id":"invented"}'
            result = self.runtime.run_query("What is the timeout?", [page.url], "4")
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["citations"], [])
            self.assertEqual(result["metrics"]["input_tokens"], 10)
            self.assertEqual(result["metrics"]["output_tokens"], 8)

    def test_existing_runtime_does_not_install_or_spawn(self):
        models = {"models": [{"name": MODEL, "digest": MODEL_DIGEST}]}
        with patch("demo.bootstrap._version", return_value="fixture-version"), patch(
                "demo.bootstrap._api", return_value=models), patch("demo.bootstrap._install_binary") as install, patch(
                "demo.bootstrap.subprocess.Popen") as spawn:
            self.runtime.ensure_ready()
        self.assertEqual(self.runtime.version, "fixture-version")
        install.assert_not_called()
        spawn.assert_not_called()

    def test_missing_model_is_pulled_once_and_digest_is_checked(self):
        models = {"models": [{"name": MODEL, "digest": "sha256:" + MODEL_DIGEST}]}
        with patch("demo.bootstrap._version", return_value="fixture"), patch(
                "demo.bootstrap._api", side_effect=[{"models": []}, {"status": "success"}, models]) as api:
            self.runtime.ensure_ready()
        self.assertEqual(api.call_args_list[1].args, ("/api/pull", {"model": MODEL, "stream": False}))
        for models in ({"models": [{"name": MODEL, "digest": "unverified"}]}, {"models": "invalid"}):
            with self.subTest(models=models), patch("demo.bootstrap._version", return_value="fixture"), patch(
                    "demo.bootstrap._api", return_value=models), self.assertRaises(RuntimeUnavailable):
                self.runtime.ensure_ready()

    def test_nonlinux_without_existing_service_has_a_useful_setup_failure(self):
        with patch("demo.bootstrap._version", return_value=None), patch("demo.bootstrap.platform.system", return_value="Windows"), patch(
                "demo.bootstrap._install_binary") as install, self.assertRaisesRegex(RuntimeUnavailable, "Start local Ollama"):
            self.runtime.ensure_ready()
        install.assert_not_called()


class BootstrapTests(unittest.TestCase):
    def archive(self, entries):
        source = io.BytesIO()
        with tarfile.open(fileobj=source, mode="w") as archive:
            for name, kind, body in entries:
                member = tarfile.TarInfo(name)
                member.type = kind
                member.mode = 0o755
                if kind == tarfile.REGTYPE:
                    member.size = len(body)
                    archive.addfile(member, io.BytesIO(body))
                else:
                    member.linkname = body
                    archive.addfile(member)
        source.seek(0)
        return tarfile.open(fileobj=source, mode="r|")

    def test_extracts_regular_files_with_executable_permissions(self):
        with tempfile.TemporaryDirectory() as temporary, self.archive([
                ("bin/ollama", tarfile.REGTYPE, b"fixture executable"),
                ("lib/ollama/library.so", tarfile.REGTYPE, b"fixture library")]) as archive:
            root = Path(temporary)
            _extract_tar(archive, root)
            self.assertEqual((root / "bin/ollama").read_bytes(), b"fixture executable")
            self.assertEqual((root / "lib/ollama/library.so").read_bytes(), b"fixture library")

    def test_rejects_traversal_absolute_paths_links_and_special_files(self):
        for name, kind, body in (("../outside", tarfile.REGTYPE, b"bad"), ("/outside", tarfile.REGTYPE, b"bad"),
                                 ("..\\outside", tarfile.REGTYPE, b"bad"), ("bin/ollama", tarfile.SYMTYPE, "../../outside"),
                                 ("bin/ollama", tarfile.LNKTYPE, "../outside"), ("device", tarfile.CHRTYPE, "")):
            with self.subTest(name=name, kind=kind), tempfile.TemporaryDirectory() as temporary, self.archive(
                    [(name, kind, body)]) as archive, self.assertRaises(RuntimeUnavailable):
                _extract_tar(archive, Path(temporary))

    def test_bad_download_checksum_cannot_extract_or_launch(self):
        with tempfile.TemporaryDirectory() as temporary, patch("demo.bootstrap.urllib.request.urlopen", return_value=io.BytesIO(b"invalid")), patch(
                "demo.bootstrap.ARCHIVE_BYTES", 7), patch("demo.bootstrap._extract_tar") as extract, self.assertRaisesRegex(
                RuntimeUnavailable, "checksum"):
            _install_binary(Path(temporary))
        extract.assert_not_called()
        self.assertEqual(len(ARCHIVE_SHA256), 64)

    def test_setup_api_uses_fixed_loopback_and_rejects_malformed_or_large_reply(self):
        opener = type("Opener", (), {"open": lambda _, request, timeout: io.BytesIO(b'{"status":"success"}')})()
        with patch("demo.bootstrap.urllib.request.build_opener", return_value=opener):
            self.assertEqual(_api("/api/pull", {"model": MODEL, "stream": False}), {"status": "success"})
        for body in (b'[]', b'{"error":"failed"}', b' ' * 2_000_001):
            opener = type("Opener", (), {"open": lambda _, request, timeout: io.BytesIO(body)})()
            with self.subTest(size=len(body)), patch("demo.bootstrap.urllib.request.build_opener", return_value=opener), self.assertRaises(
                    RuntimeUnavailable):
                _api("/api/tags")


if __name__ == "__main__":
    unittest.main()
