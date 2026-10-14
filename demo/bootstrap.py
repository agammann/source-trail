"""User-writable, checksum-pinned Ollama bootstrap for the optional demo."""

import atexit
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import subprocess
import tarfile
import tempfile
import threading
import time
import urllib.error
import urllib.request

from sourcetrail.engine import query
from demo.selector import ExtractiveSelector, strict_json

MODEL = "qwen3:0.6b"
MODEL_DIGEST = "7df6b6e09427a769808717c0a93cadc4ae99ed4eb8bf5ca557c90846becea435"
ENDPOINT = "http://127.0.0.1:11434"
OLLAMA_VERSION = "0.40.3"
ARCHIVE_URL = "https://github.com/ollama/ollama/releases/download/v0.40.3/ollama-linux-amd64.tar.zst"
ARCHIVE_BYTES = 1_437_349_190
ARCHIVE_SHA256 = "ce6f8b671a699bf1ebafb28d60dbbabf4f37b30b499145fa308a8ba72de021d6"
PAGE_BUDGET = 3


class RuntimeUnavailable(RuntimeError):
    pass


class DemoBusy(RuntimeError):
    pass


def _api(path, payload=None, timeout=5):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(ENDPOINT + path, data=data,
                                     headers={"Content-Type": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=timeout) as response:
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise RuntimeUnavailable("The local model service returned an oversized response.")
    body = strict_json(raw)
    if not isinstance(body, dict) or body.get("error"):
        raise RuntimeUnavailable("The local model service could not complete its setup request.")
    return body


def _version():
    try:
        version = _api("/api/version").get("version")
        return version if isinstance(version, str) and version else None
    except (OSError, ValueError, RuntimeUnavailable):
        return None


def _safe_member_path(root, name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name:
        raise RuntimeUnavailable("The pinned runtime archive contained an unsafe path.")
    target = (root / str(path)).resolve()
    if not target.is_relative_to(root.resolve()):
        raise RuntimeUnavailable("The pinned runtime archive escaped its installation folder.")
    return target


def _extract_tar(archive, destination):
    # Extract only ordinary files/directories first. Links cannot redirect later writes.
    links = []
    for member in archive:
        target = _safe_member_path(destination, member.name)
        if member.isdir():
            target.mkdir(parents=True, exist_ok=True)
        elif member.isfile():
            target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise RuntimeUnavailable("The pinned runtime archive contained an unreadable file.")
            with source, target.open("wb") as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)
            target.chmod(member.mode & 0o777)
        elif member.issym() or member.islnk():
            links.append((member, target))
        else:
            raise RuntimeUnavailable("The pinned runtime archive contained an unsupported entry.")
    for member, target in links:
        link = PurePosixPath(member.linkname)
        if link.is_absolute() or "\\" in member.linkname:
            raise RuntimeUnavailable("The pinned runtime archive contained an unsafe link.")
        linked = (target.parent / str(link)).resolve() if member.issym() else _safe_member_path(destination, member.linkname)
        if not linked.is_relative_to(destination.resolve()):
            raise RuntimeUnavailable("The pinned runtime archive contained an escaping link.")
        target.parent.mkdir(parents=True, exist_ok=True)
        if member.issym():
            target.symlink_to(member.linkname)
        else:
            os.link(linked, target)


def _install_binary(cache):
    installation = cache / ("ollama-" + OLLAMA_VERSION)
    binary = installation / "bin" / "ollama"
    if binary.is_file():
        return binary
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="runtime-", dir=cache) as temporary:
        temporary = Path(temporary)
        archive_path = temporary / "runtime.tar.zst"
        digest, received = hashlib.sha256(), 0
        deadline = time.monotonic() + 600
        with urllib.request.urlopen(ARCHIVE_URL, timeout=30) as response, archive_path.open("wb") as output:
            while True:
                if time.monotonic() > deadline:
                    raise RuntimeUnavailable("Runtime download exceeded its startup time limit.")
                block = response.read(1024 * 1024)
                if not block:
                    break
                received += len(block)
                if received > ARCHIVE_BYTES:
                    raise RuntimeUnavailable("Runtime download exceeded its pinned size.")
                digest.update(block)
                output.write(block)
        if received != ARCHIVE_BYTES or digest.hexdigest() != ARCHIVE_SHA256:
            raise RuntimeUnavailable("Runtime download did not match the pinned release checksum.")
        import zstandard
        staged = temporary / "installation"
        staged.mkdir()
        with archive_path.open("rb") as source, zstandard.ZstdDecompressor().stream_reader(source) as stream:
            with tarfile.open(fileobj=stream, mode="r|") as archive:
                _extract_tar(archive, staged)
        if not (staged / "bin" / "ollama").is_file():
            raise RuntimeUnavailable("The pinned runtime archive did not include Ollama.")
        # A previous incomplete folder may survive a reboot; replace only this fixed cache subfolder.
        if installation.exists():
            if not installation.resolve().is_relative_to(cache.resolve()):
                raise RuntimeUnavailable("The runtime cache installation path is outside its cache folder.")
            shutil.rmtree(installation)
        staged.rename(installation)
    return binary


class DemoRuntime:
    def __init__(self, cache=None):
        self.cache = Path(cache) if cache is not None else Path.home() / ".cache" / "source-trail-demo"
        self.lock = threading.Lock()
        self.process = None
        self.version = None
        atexit.register(self.close)

    def close(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)

    def ensure_ready(self):
        self.version = _version()
        if self.version is None:
            if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
                raise RuntimeUnavailable("Start local Ollama before running this demonstration on this computer.")
            binary = _install_binary(self.cache)
            environment = os.environ.copy()
            environment.update({"OLLAMA_HOST": "127.0.0.1:11434", "OLLAMA_MODELS": str(self.cache / "models"),
                                "OLLAMA_NO_CLOUD": "1", "OLLAMA_NUM_PARALLEL": "1",
                                "OLLAMA_MAX_LOADED_MODELS": "1", "OLLAMA_MAX_QUEUE": "1"})
            with (self.cache / "ollama.log").open("ab") as log:
                self.process = subprocess.Popen([str(binary), "serve"], env=environment, stdout=log, stderr=log)
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise RuntimeUnavailable("The local runtime exited during startup.")
                self.version = _version()
                if self.version:
                    break
                time.sleep(0.25)
            if not self.version:
                self.close()
                raise RuntimeUnavailable("The local runtime did not become ready within its startup limit.")
        models = _api("/api/tags").get("models")
        if not isinstance(models, list):
            raise RuntimeUnavailable("The local runtime returned an invalid model list.")
        selected = next((entry for entry in models if isinstance(entry, dict) and entry.get("name") == MODEL), None)
        if selected is None:
            if _api("/api/pull", {"model": MODEL, "stream": False}, timeout=600).get("status") != "success":
                raise RuntimeUnavailable("The demonstration model could not be downloaded.")
            models = _api("/api/tags").get("models", [])
            if not isinstance(models, list):
                raise RuntimeUnavailable("The local runtime returned an invalid model list after download.")
            selected = next((entry for entry in models if isinstance(entry, dict) and entry.get("name") == MODEL), None)
        if selected is None or str(selected.get("digest", "")).removeprefix("sha256:") != MODEL_DIGEST:
            raise RuntimeUnavailable("The demonstration model did not match its pinned registry digest.")

    def run_query(self, question, urls, target_version=None):
        if not self.lock.acquire(blocking=False):
            raise DemoBusy("Another query is running. Please try again after it finishes.")
        try:
            selector = ExtractiveSelector(self, MODEL, _api)
            result = query(question, urls, target_version=target_version, mode="verified",
                           max_pages=PAGE_BUDGET, allow_local=False, model=selector)
            result["metrics"].update(selector.metrics)
            result["demo_runtime"] = {"model": MODEL, "model_digest": MODEL_DIGEST,
                                      "provider": "local Ollama", "ollama_version": self.version if selector.metrics["model_calls"] else None,
                                      "profile": "single-passage extraction; CPU hosting target",
                                      "page_budget": PAGE_BUDGET, "candidate_limit": 4,
                                      "context_tokens": 4096, "max_generated_tokens": 64}
            result["demo_selection"] = selector.selection
            return result
        finally:
            self.lock.release()


if __name__ == "__main__":
    runtime = DemoRuntime()
    with runtime.lock:
        runtime.ensure_ready()
    print(f"Local Ollama {runtime.version} has the pinned {MODEL} model ready.")
