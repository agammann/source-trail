"""Record a bounded Source Trail development run in the AMD tutorial VM."""

import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request


def now():
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--expected-revision", required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    root = source.parent
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
    if revision != args.expected_revision:
        raise SystemExit("The source revision does not match the tested commit.")
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=source, text=True).strip():
        raise SystemExit("The source checkout must be clean.")
    result_dir = root / "results"
    result_dir.mkdir(exist_ok=True)
    raw_dir = result_dir / "provider"
    raw_dir.mkdir(exist_ok=True)
    counter = 0
    lock = threading.Lock()

    class Recorder(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            nonlocal counter
            if self.path != "/v1/chat/completions":
                self.send_error(404)
                return
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 2_000_000:
                self.send_error(413)
                return
            payload = self.rfile.read(size)
            with lock:
                counter += 1
                index = counter
            started = now()
            record = {"sequence": index, "request_started_utc": started,
                      "request": json.loads(payload)}
            request = urllib.request.Request("http://127.0.0.1:8000" + self.path,
                                             data=payload, method="POST",
                                             headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    status = response.status
                    body = response.read(2_000_001)
            except urllib.error.HTTPError as error:
                status, body = error.code, error.read(2_000_001)
            except Exception as error:
                record.update(response_finished_utc=now(), error=type(error).__name__)
                (raw_dir / f"request-{index:03}.json").write_text(json.dumps(record, indent=2))
                self.send_error(502)
                return
            record.update(response_finished_utc=now(), http_status=status)
            try:
                record["response"] = json.loads(body)
            except ValueError:
                record["invalid_response_text"] = body.decode("utf-8", errors="replace")
            (raw_dir / f"request-{index:03}.json").write_text(json.dumps(record, indent=2))
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    relay = ThreadingHTTPServer(("127.0.0.1", 8001), Recorder)
    relay_thread = threading.Thread(target=relay.serve_forever, daemon=True)
    relay_thread.start()
    stop = threading.Event()
    activity = []

    def sample_gpu():
        while not stop.is_set():
            stamp = now()
            try:
                sample = subprocess.run(["amd-smi", "monitor", "-u", "-m", "-v", "-q", "--json"],
                                        capture_output=True, text=True, timeout=15)
                activity.append({"sample_started_utc": stamp, "sample_finished_utc": now(),
                                 "exit_code": sample.returncode,
                                 "data": json.loads(sample.stdout)})
            except Exception as error:
                activity.append({"sample_started_utc": stamp, "error": type(error).__name__})
            stop.wait(0.25)

    env = os.environ.copy()
    env.update(SOURCETRAIL_PROVIDER="vllm", SOURCETRAIL_VLLM_URL="http://127.0.0.1:8001/v1",
               SOURCETRAIL_MODEL="Qwen3-4B-Instruct-2507")
    env.pop("SOURCETRAIL_VLLM_API_KEY", None)
    commands = [
        ("unit", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]),
        ("public-taskgroup", [sys.executable, "-m", "sourcetrail", "query", "--question",
          "What happens to other tasks when one task in a TaskGroup fails?", "--url",
          "https://docs.python.org/3/library/asyncio-task.html", "--mode", "verified",
          "--max-pages", "6", "--model", "Qwen3-4B-Instruct-2507", "--output",
          str(result_dir / "live-python-taskgroup.json")]),
        ("synthetic", [sys.executable, "-m", "benchmark.run", "--report-dir",
          str(result_dir / "synthetic"), "--modes", "baseline", "verified", "--model",
          "Qwen3-4B-Instruct-2507"]),
        ("stress", [sys.executable, "-m", "benchmark.holdout.run", "--run-model", "--report-dir",
          str(result_dir / "stress"), "--modes", "baseline", "verified", "--model",
          "Qwen3-4B-Instruct-2507"]),
    ]
    records = []
    try:
        for name, command in commands:
            print("START", name, flush=True)
            if name == "public-taskgroup":
                before = urllib.request.urlopen("http://127.0.0.1:8000/metrics", timeout=5).read()
                (result_dir / "server-metrics-before.txt").write_bytes(before)
                sampler = threading.Thread(target=sample_gpu, daemon=True)
                sampler.start()
            started = now()
            process_env = env
            if name == "unit":
                process_env = os.environ.copy()
                for key in ("SOURCETRAIL_PROVIDER", "SOURCETRAIL_MODEL", "SOURCETRAIL_VLLM_URL", "SOURCETRAIL_VLLM_API_KEY"):
                    process_env.pop(key, None)
            proc = subprocess.run(command, cwd=source, env=process_env, capture_output=True,
                                  text=True, timeout=900)
            (result_dir / f"{name}.stdout.txt").write_text(proc.stdout)
            (result_dir / f"{name}.stderr.txt").write_text(proc.stderr)
            records.append({"name": name, "command": command, "started_utc": started,
                            "finished_utc": now(), "exit_code": proc.returncode})
            print("DONE", name, "exit", proc.returncode, flush=True)
            if name == "unit" and proc.returncode:
                break
        after = urllib.request.urlopen("http://127.0.0.1:8000/metrics", timeout=5).read()
        (result_dir / "server-metrics-after.txt").write_bytes(after)
    finally:
        stop.set()
        if "sampler" in locals():
            sampler.join(timeout=20)
        relay.shutdown()
        relay.server_close()
        (result_dir / "gpu-activity.json").write_text(json.dumps(activity, indent=2))
        manifest = {"source_revision": revision, "source_clean_before_run": True,
                    "model": env["SOURCETRAIL_MODEL"], "provider": "vllm",
                    "provider_requests": counter, "commands": records,
                    "gpu_samples": len(activity), "classification": "development validation",
                    "official_evaluator": False,
                    "note": "The recording relay stores the unmodified local vLLM request and response. "
                            "Unit tests use stubs; model calls belong to the following query and development suites."}
        (result_dir / "validation.json").write_text(json.dumps(manifest, indent=2))
        print(json.dumps(manifest, indent=2), flush=True)


if __name__ == "__main__":
    main()
