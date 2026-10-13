from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import socket
import threading
import time
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from sourcetrail.web import Page, WebReader, WebReadError, _PinnedConnection


HTML = b"""<!doctype html><html><head><title>Source &amp; Trail</title>
<style>.x { content: 'STYLE SECRET'; }</style><script>SCRIPT SECRET</script></head>
<body><title>Embedded document title</title><h1>Plans <em>and pricing</em></h1><p>Full inter<strong>oper</strong>ability costs <b>$12</b> per month.</p>
<table><tr><th>Plan</th><th>Price</th></tr><tr><td>Starter</td><td>$12<span>/mo</span></td></tr></table>
<ul><li>Keep <strong>two</strong> copies.</li></ul>
<p>Visible <span hidden>HIDDEN SECRET</span>text.</p>
<div aria-hidden="true"><p>ARIA SECRET</p></div><div style="display: none !important"><p>DISPLAY SECRET</p></div>
<span style="visibility: hidden">VISIBILITY SECRET</span><noscript>NOSCRIPT SECRET</noscript><template>TEMPLATE SECRET</template>
<p><a href="/text#top">Read <b>the text</b></a> and <a href="/text#other">Duplicate</a>.</p>
<a href="/next?rate=12&amp;currency=USD">Next</a><a href="https://outside.example/path">Outside</a>
<a href="javascript:alert(1)">Script link</a><a href="mailto:user@example.com">Email</a>
<a href="http://user:secret@127.0.0.1/private">Credentials</a>
<p>Repeated notice</p><p>Repeated notice</p></body></html>"""


class FixtureHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        path = urlsplit(self.path).path
        if path in {"/redirect", "/outside", "/loop", "/hops", "/slow-hop"}:
            if path == "/redirect":
                location = "/html"
            elif path == "/outside":
                location = f"http://localhost:{self.server.server_port}/html"
            elif path == "/loop":
                location = "/loop"
            else:
                count = int(parse_qs(urlsplit(self.path).query).get("count", ["0"])[0])
                location = f"{path}?count={count + 1}"
            if path == "/slow-hop":
                time.sleep(0.04)
            self.send_response(302)
            self.send_header("Location", location)
            self.end_headers()
            return
        content_type = "text/plain; charset=utf-8"
        body = b"First paragraph.\nStill first.\n\nSecond paragraph."
        status = 200
        if path == "/html":
            content_type, body = "text/html; charset=utf-8", HTML
        elif path == "/latin":
            content_type, body = "text/plain; charset=iso-8859-1", "caf\u00e9\n\nPrice $12".encode("iso-8859-1")
        elif path == "/unknown-charset":
            content_type, body = "text/plain; charset=made-up-codec", "caf\u00e9".encode()
        elif path in {"/large", "/unknown-size"}:
            body = b"x" * 1000
        elif path == "/exact":
            body = b"x" * 32
        elif path == "/binary":
            content_type, body = "application/octet-stream", b"\x00\x01"
        elif path == "/missing":
            status, body = 404, b"Missing"
        elif path == "/deep":
            content_type, body = "text/html", b"<div>" * 300 + b"deep"
        elif path == "/malformed-link":
            content_type, body = "text/html", b'<p>The confirmed price is $12.</p><a href="http://[broken/">Broken</a><a href="/text">Valid</a>'
        elif path == "/empty-table-cell":
            content_type, body = "text/html", b'<table><tr><th>Plan</th><th>Price</th></tr><tr><td></td><td>12 dollars</td></tr></table>'
        elif path == "/adjacent-tables":
            content_type, body = "text/html", b'<h2>Prices</h2><table><tr><th>Item</th><th>USD</th></tr><tr><td>Basic</td><td>12</td></tr></table><table><tr><th>Item</th><th>EUR</th></tr><tr><td>Basic</td><td>20</td></tr></table><p>Terms apply.</p>'
        elif path == "/paragraph-table-cells":
            content_type, body = "text/html", b'<h2>Prices</h2><table><tr><th>Item</th><th>USD</th></tr><tr><td><p>Basic</p><p>plan</p></td><td><p>12 <em>dollars</em></p></td></tr></table>'
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        if path == "/compressed":
            self.send_header("Content-Encoding", "gzip")
        if path != "/unknown-size":
            self.send_header("Content-Length", str(len(body) + (20 if path == "/short-response" else 0)))
        self.end_headers()
        if path == "/slow":
            time.sleep(0.2)
        try:
            if path == "/trickle":
                for i in range(0, len(body), 5):
                    self.wfile.write(body[i:i + 5])
                    self.wfile.flush()
                    time.sleep(0.02)
            else:
                self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass


class WebReaderFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def reader(self, **kwargs):
        return WebReader(["127.0.0.1"], allow_local=True, **kwargs)

    def test_html_preserves_inline_text_and_table_relationships(self):
        page = self.reader().fetch(self.base + "/html")
        self.assertIsInstance(page, Page)
        self.assertEqual(page.title, "Source & Trail")
        self.assertIn("Plans and pricing", page.blocks)
        self.assertIn("Full interoperability costs $12 per month.", page.blocks)
        self.assertIn("Plan | Price", page.blocks)
        self.assertIn("Starter | $12/mo", page.blocks)
        self.assertIn("Keep two copies.", page.blocks)
        self.assertIn("Visible text.", page.blocks)
        self.assertNotIn("SECRET", " ".join(page.blocks))
        self.assertEqual(page.blocks.count("Repeated notice"), 2)
        self.assertEqual(page.sha256, sha256(HTML).hexdigest())
        self.assertEqual(page.content_type, "text/html")
        self.assertGreaterEqual(page.elapsed_ms, 0)
        self.assertFalse(page.truncated)

    def test_links_are_resolved_scoped_and_deduplicated(self):
        page = self.reader().fetch(self.base + "/html")
        self.assertEqual(page.links, [
            {"url": self.base + "/text", "label": "Read the text"},
            {"url": self.base + "/next?rate=12&currency=USD", "label": "Next"},
        ])

    def test_malformed_link_does_not_discard_readable_evidence(self):
        page = self.reader().fetch(self.base + "/malformed-link")
        self.assertIn("The confirmed price is $12.", page.blocks)
        self.assertEqual(page.links, [{"url": self.base + "/text", "label": "Valid"}])

    def test_incomplete_response_is_a_read_failure_not_complete_evidence(self):
        with self.assertRaisesRegex(WebReadError, "declared content length"):
            self.reader().fetch(self.base + "/short-response")

    def test_empty_first_table_cell_preserves_the_value_column(self):
        page = self.reader().fetch(self.base + "/empty-table-cell")
        self.assertIn("Plan | Price", page.blocks)
        self.assertIn("| 12 dollars", page.blocks)
        self.assertNotIn("12 dollars", page.blocks)

    def test_adjacent_tables_retain_distinct_identities_without_visible_separators(self):
        page = self.reader().fetch(self.base + "/adjacent-tables")
        self.assertEqual(page.blocks, ["Prices", "Item | USD", "Basic | 12", "Item | EUR", "Basic | 20", "Terms apply."])
        self.assertEqual(page.block_tags, ["h2", "tr", "tr", "tr", "tr", "p"])
        self.assertEqual(page.block_tables, [None, 1, 1, 2, 2, None])

    def test_paragraph_markup_inside_cells_preserves_one_row_and_column_context(self):
        page = self.reader().fetch(self.base + "/paragraph-table-cells")
        self.assertEqual(page.blocks, ["Prices", "Item | USD", "Basic plan | 12 dollars"])
        self.assertEqual(page.block_tags, ["h2", "tr", "tr"])
        self.assertEqual(page.block_tables, [None, 1, 1])

    def test_plain_text_and_charset_decoding(self):
        page = self.reader().fetch(self.base + "/text")
        self.assertEqual(page.blocks, ["First paragraph. Still first.", "Second paragraph."])
        self.assertEqual(page.links, [])
        self.assertEqual(page.title, "")
        self.assertEqual(page.block_tables, [None, None])
        self.assertEqual(self.reader().fetch(self.base + "/latin").blocks, ["caf\u00e9", "Price $12"])
        self.assertEqual(self.reader().fetch(self.base + "/unknown-charset").blocks, ["caf\u00e9"])

    def test_same_host_redirect_returns_final_source_url(self):
        page = self.reader().fetch(self.base + "/redirect")
        self.assertEqual(page.url, self.base + "/html")
        self.assertEqual(page.title, "Source & Trail")

    def test_redirect_cannot_leave_exact_host_scope(self):
        with self.assertRaisesRegex(WebReadError, "outside the allowed scope"):
            self.reader().fetch(self.base + "/outside")

    def test_redirect_loop_and_hop_cap(self):
        with self.assertRaisesRegex(WebReadError, "redirect loop"):
            self.reader().fetch(self.base + "/loop")
        with self.assertRaisesRegex(WebReadError, "too many redirects"):
            self.reader().fetch(self.base + "/hops")

    def test_download_cap_and_digest_apply_to_received_prefix(self):
        for path in {"/large", "/unknown-size"}:
            with self.subTest(path=path):
                page = self.reader(max_bytes=32).fetch(self.base + path)
                self.assertEqual(page.blocks, ["x" * 32])
                self.assertEqual(page.sha256, sha256(b"x" * 32).hexdigest())
                self.assertTrue(page.truncated)
        self.assertFalse(self.reader(max_bytes=32).fetch(self.base + "/exact").truncated)

    def test_unsupported_response_and_http_failure_have_safe_errors(self):
        for path, message in [("/binary", "not supported"), ("/compressed", "Compressed"), ("/missing", "HTTP 404"), ("/deep", "excessive HTML nesting")]:
            with self.subTest(path=path), self.assertRaisesRegex(WebReadError, message):
                self.reader().fetch(self.base + path)

    def test_network_timeout_is_sanitized(self):
        with self.assertRaisesRegex(WebReadError, "could not be read"):
            self.reader(timeout=0.05).fetch(self.base + "/slow?token=private-value")

    def test_total_deadline_stops_an_active_trickling_response(self):
        started = time.monotonic()
        with self.assertRaisesRegex(WebReadError, "total time budget"):
            self.reader(timeout=0.08).fetch(self.base + "/trickle")
        self.assertLess(time.monotonic() - started, 0.3)

    def test_redirect_hops_share_one_total_deadline(self):
        started = time.monotonic()
        with self.assertRaisesRegex(WebReadError, "total time budget"):
            self.reader(timeout=0.09).fetch(self.base + "/slow-hop")
        self.assertLess(time.monotonic() - started, 0.3)


class WebReaderScopeTests(unittest.TestCase):
    def test_schemes_credentials_ports_and_subdomains_are_rejected_before_network(self):
        reader = WebReader(["example.com"])
        urls = [
            "file:///private", "ftp://example.com/file", "http://user:secret@example.com/",
            "http://example.com:8080/", "https://example.com:80/", "https://child.example.com/",
            "https://example.com.evil.test/", "https://example.com/\r\nInjected: yes",
        ]
        with patch("sourcetrail.web.socket.getaddrinfo") as resolve:
            for url in urls:
                with self.subTest(url=url), self.assertRaises(WebReadError) as failure:
                    reader.fetch(url)
                self.assertNotIn("secret", str(failure.exception))
            resolve.assert_not_called()

    def test_local_dns_addresses_require_explicit_fixture_opt_in(self):
        reader = WebReader(["fixture.example"])
        for address in ["127.0.0.1", "10.0.0.2", "192.168.1.1", "169.254.169.254", "100.64.0.1", "::1", "fc00::1", "224.0.0.1", "ff0e::1"]:
            family = socket.AF_INET6 if ":" in address else socket.AF_INET
            with self.subTest(address=address), patch("sourcetrail.web.socket.getaddrinfo", return_value=[(family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, 80))]), patch("sourcetrail.web._PinnedConnection") as connection:
                with self.assertRaisesRegex(WebReadError, "non-public address"):
                    reader.fetch("http://fixture.example/")
                connection.assert_not_called()

    def test_mixed_public_and_private_dns_records_are_rejected(self):
        records = [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", 80)),
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", 80)),
        ]
        with patch("sourcetrail.web.socket.getaddrinfo", return_value=records), self.assertRaisesRegex(WebReadError, "non-public address"):
            WebReader(["fixture.example"]).fetch("http://fixture.example/")

    def test_every_redirect_revalidates_dns_before_the_next_connection(self):
        public_record = [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", 80))]
        private_record = [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", 80))]
        response = Mock(status=302)
        response.getheader.return_value = "/destination"
        connection = Mock()
        connection.getresponse.return_value = response
        with patch("sourcetrail.web.socket.getaddrinfo", side_effect=[public_record, private_record]) as resolve, patch("sourcetrail.web._PinnedConnection", return_value=connection) as connect:
            with self.assertRaisesRegex(WebReadError, "non-public address"):
                WebReader(["fixture.example"]).fetch("http://fixture.example/start")
            self.assertEqual(resolve.call_count, 2)
            self.assertEqual(connect.call_count, 1)
            connection.close.assert_called_once()

    def test_connections_use_prevalidated_ip_instead_of_resolving_the_host_again(self):
        approved_ip = "93.184.216.34"
        connection = _PinnedConnection("fixture.example", 80, [approved_ip], 1, secure=False)
        fake_socket = Mock()
        with patch("sourcetrail.web.socket.create_connection", return_value=fake_socket) as create, patch("sourcetrail.web.socket.getaddrinfo") as resolve:
            connection.connect()
            self.assertEqual(create.call_args.args[0], (approved_ip, 80))
            resolve.assert_not_called()
        connection.close()

    def test_invalid_configuration_is_rejected(self):
        for options in [dict(allowed_hosts=[]), dict(allowed_hosts=["https://example.com"]), dict(allowed_hosts=["example.com"], max_bytes=0), dict(allowed_hosts=["example.com"], timeout=float("nan"))]:
            with self.subTest(options=options), self.assertRaises(WebReadError):
                WebReader(**options)

    def test_dns_wait_uses_the_fetch_deadline_without_connecting_after_timeout(self):
        def slow_resolution(*args, **kwargs):
            time.sleep(0.3)
            return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", 80))]

        started = time.monotonic()
        with patch("sourcetrail.web.socket.getaddrinfo", side_effect=slow_resolution), patch("sourcetrail.web._PinnedConnection") as connection:
            with self.assertRaisesRegex(WebReadError, "total time budget"):
                WebReader(["fixture.example"], timeout=0.05).fetch("http://fixture.example/")
            connection.assert_not_called()
        self.assertLess(time.monotonic() - started, 0.25)


if __name__ == "__main__":
    unittest.main()
