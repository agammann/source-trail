"""Loopback-only inspector; source requests remain scoped by the query engine."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from urllib.parse import urlsplit

from .engine import query

ROOT = Path(__file__).parent / "static"
QUERY_LOCK = threading.Lock()


def make_handler(allow_local=False):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send_data(self, status, body, content_type="application/json; charset=utf-8"):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(body)

        def json(self, status, value):
            self.send_data(status, json.dumps(value, ensure_ascii=False).encode("utf-8"))

        def trusted_request(self):
            try:
                host = urlsplit("http://" + self.headers.get("Host", ""))
                if host.hostname not in {"localhost", "127.0.0.1", "::1"} or host.port != self.server.server_port:
                    return False
                origin = self.headers.get("Origin")
                return not origin or (urlsplit(origin).netloc == host.netloc and urlsplit(origin).scheme == "http")
            except ValueError:
                return False

        def do_GET(self):
            if not self.trusted_request():
                return self.json(403, {"error": "Local origin required."})
            if self.path == "/api/health":
                return self.json(200, {"status": "ok", "name": "Source Trail", "stage": "pre-brief prototype"})
            if self.path in {"/", "/index.html"}:
                return self.send_data(200, (ROOT / "index.html").read_bytes(), "text/html; charset=utf-8")
            self.json(404, {"error": "Not found."})

        def do_POST(self):
            if self.path != "/api/query":
                return self.json(404, {"error": "Not found."})
            if not self.trusted_request():
                return self.json(403, {"error": "Local origin required."})
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                return self.json(415, {"error": "JSON required."})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 12000:
                    return self.json(413, {"error": "Request size must be between 1 and 12000 bytes."})
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict):
                    raise ValueError("Expected a JSON object.")
                if not QUERY_LOCK.acquire(blocking=False):
                    return self.json(429, {"error": "A query is already running. Try again after it finishes."})
                try:
                    target_version = data.get("target_version")
                    if isinstance(target_version, str) and target_version == "":
                        target_version = None
                    result = query(data.get("question"), data.get("urls"), target_version,
                                   data.get("mode", "verified"), data.get("max_pages", 6), allow_local)
                    self.json(200, result)
                finally:
                    QUERY_LOCK.release()
            except (ValueError, TypeError) as exc:
                self.json(400, {"error": str(exc)})
            except Exception:
                self.json(500, {"error": "Query could not be completed."})

    return Handler


def serve(host="127.0.0.1", port=8765, allow_local=False):
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("Use 127.0.0.1 or localhost for the inspector.")
    server = ThreadingHTTPServer((host, port), make_handler(allow_local))
    print(f"Source Trail is available at http://{host}:{port}", flush=True)
    server.serve_forever()
