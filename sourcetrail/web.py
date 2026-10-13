"""Bounded, scoped acquisition of public HTML and plain-text pages."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from html.parser import HTMLParser
import http.client
import ipaddress
import math
import queue
import re
import socket
import ssl
import threading
import time
from urllib.parse import quote, urljoin, urlsplit, urlunsplit


@dataclass(frozen=True)
class Page:
    url: str
    title: str
    blocks: list[str]
    links: list[dict[str, str]]
    elapsed_ms: int
    sha256: str
    content_type: str
    truncated: bool
    block_tags: list[str] = field(default_factory=list)
    block_tables: list[int | None] = field(default_factory=list)


class WebReadError(ValueError):
    """A scoped or unsuccessful read, with no request credentials in its message."""


class _FetchDeadline:
    """Bound DNS waiting and interrupt socket reads across the whole redirect chain."""

    def __init__(self, seconds: float) -> None:
        self.started = time.monotonic()
        self.expires = self.started + seconds
        self.expired = threading.Event()
        self.connection: _PinnedConnection | None = None
        self.socket: socket.socket | None = None
        self.timer = threading.Timer(seconds, self._abort)
        self.timer.daemon = True

    def _abort(self) -> None:
        self.expired.set()
        # HTTPResponse may own a makefile after HTTPConnection closes its socket.
        # Keep the socket reference so shutdown interrupts that response as well.
        sockets = [self.socket]
        if self.connection is not None:
            sockets.append(self.connection.sock)
        for active in sockets:
            if active is not None:
                try:
                    active.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                try:
                    active.close()
                except OSError:
                    pass

    def remaining(self) -> float:
        remaining = self.expires - time.monotonic()
        if self.expired.is_set() or remaining <= 0:
            raise WebReadError("The page could not be read within its total time budget.")
        return remaining

    def __enter__(self) -> _FetchDeadline:
        self.timer.start()
        return self

    def __exit__(self, *_) -> None:
        self.timer.cancel()
        self.connection = None
        self.socket = None


def _host_name(value: str) -> str:
    value = value.strip().rstrip(".")
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        pass
    try:
        result = value.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise WebReadError("Invalid host name.") from exc
    labels = result.split(".")
    if len(result) > 253 or not all(
        re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
        for label in labels
    ):
        raise WebReadError("Invalid host name.")
    return result


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


class _ReadableHTML(HTMLParser):
    _void = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
    _drop = {"script", "style", "noscript", "template", "svg"}
    _blocks = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "blockquote", "pre", "dt", "dd", "figcaption", "div", "section", "article", "main", "header", "footer", "aside", "nav", "ul", "ol", "table"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.blocks: list[str] = []
        self.block_tags: list[str] = []
        self.block_tables: list[int | None] = []
        self.links: list[dict[str, str]] = []
        self._stack: list[tuple[str, bool]] = []
        self._text: list[str] = []
        self._title_text: list[str] = []
        self._saw_title = False
        self._title_depth: int | None = None
        self._anchor: dict[str, object] | None = None
        self._row_cells: dict[int, int] = {}
        self._tables: dict[int, int] = {}
        self._next_table = 1

    @property
    def _blocked(self) -> bool:
        return bool(self._stack and self._stack[-1][1])

    def _flush(self, force: bool = False) -> None:
        in_cell = any(tag in {"td", "th"} and not blocked for tag, blocked in self._stack)
        if in_cell and not force:
            # Paragraphs and other block markup inside a cell separate words;
            # they do not end the row or remove its column relationships.
            self._text.append(" ")
            if self._anchor is not None:
                self._anchor["text"].append(" ")
            return
        text = _clean_text("".join(self._text))
        if text:
            self.blocks.append(text)
            tag = "tr" if in_cell and any(tag == "tr" and not blocked for tag, blocked in self._stack) else next((tag for tag, blocked in reversed(self._stack) if not blocked and tag in self._blocks), "")
            self.block_tags.append(tag)
            self.block_tables.append(self._tables[max(self._tables)] if self._tables else None)
        self._text.clear()

    def _finish_anchor(self) -> None:
        if self._anchor is not None:
            self.links.append({"url": str(self._anchor["url"]), "label": _clean_text("".join(self._anchor["text"]))})
            self._anchor = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        style = re.sub(r"\s+", "", (attributes.get("style") or "").lower())
        hidden = (
            "hidden" in attributes
            or (attributes.get("aria-hidden") or "").strip().lower() == "true"
            or re.search(r"(?:^|;)(?:display:none|visibility:hidden)(?:!important)?(?:;|$)", style) is not None
        )
        blocked = self._blocked or tag in self._drop or hidden
        if not blocked:
            if tag in self._blocks:
                self._flush(force=tag in {"table", "tr"})
                if tag == "table":
                    self._tables[len(self._stack)] = self._next_table
                    self._next_table += 1
                if tag == "tr":
                    self._row_cells[len(self._stack)] = 0
            elif tag in {"td", "th"}:
                row_depth = next((i for i in range(len(self._stack) - 1, -1, -1) if self._stack[i][0] == "tr"), None)
                preceding_cells = self._row_cells.get(row_depth, 0)
                if preceding_cells or (row_depth is None and _clean_text("".join(self._text))):
                    self._text.append(" | ")
                if row_depth is not None:
                    self._row_cells[row_depth] = preceding_cells + 1
            elif tag == "br":
                self._text.append(" ")
            elif tag == "hr":
                self._flush()
            if tag == "a":
                self._finish_anchor()
                if attributes.get("href"):
                    self._anchor = {"url": attributes["href"], "text": []}
            if tag == "img" and attributes.get("alt"):
                self.handle_data(attributes["alt"])
        if tag not in self._void:
            if len(self._stack) >= 256:
                raise WebReadError("The page has excessive HTML nesting.")
            if tag == "title" and not blocked and not self._saw_title:
                self._saw_title = True
                self._title_depth = len(self._stack)
            self._stack.append((tag, blocked))

    def handle_endtag(self, tag: str) -> None:
        matching = next((i for i in range(len(self._stack) - 1, -1, -1) if self._stack[i][0] == tag), None)
        if matching is None:
            return
        frames = self._stack[matching:]
        if any(name == "a" and not blocked for name, blocked in frames):
            self._finish_anchor()
        if any(name in self._blocks and not blocked for name, blocked in frames):
            self._flush(force=any(name in {"table", "tr"} and not blocked for name, blocked in frames))
        if self._title_depth is not None and matching <= self._title_depth:
            self._title_depth = None
        self._row_cells = {depth: count for depth, count in self._row_cells.items() if depth < matching}
        self._tables = {depth: identity for depth, identity in self._tables.items() if depth < matching}
        del self._stack[matching:]

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in self._void:
            self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        if self._blocked:
            return
        if any(tag == "title" for tag, _ in self._stack):
            if self._title_depth is not None:
                self._title_text.append(data)
            return
        if any(tag == "head" for tag, _ in self._stack):
            return
        self._text.append(data)
        if self._anchor is not None:
            self._anchor["text"].append(data)

    def close(self) -> None:
        super().close()
        self._flush(force=True)
        self._finish_anchor()
        self.title = _clean_text("".join(self._title_text))


class _PinnedConnection(http.client.HTTPConnection):
    def __init__(self, host: str, port: int, addresses: list[str], timeout: float, *, secure: bool) -> None:
        super().__init__(host, port=port, timeout=timeout)
        self._addresses = addresses
        self._secure = secure

    def connect(self) -> None:
        deadline = time.monotonic() + self.timeout
        last_error: OSError | None = None
        for address in self._addresses:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Connection timed out.")
            try:
                self.sock = socket.create_connection((address, self.port), timeout=remaining)
                break
            except OSError as exc:
                last_error = exc
        else:
            raise last_error or OSError("No reachable address.")
        if self._secure:
            self.sock.settimeout(max(0.001, deadline - time.monotonic()))
            self.sock = ssl.create_default_context().wrap_socket(self.sock, server_hostname=self.host)


class WebReader:
    """Fetch exact allowed hosts, without proxies, cookies, or authorization headers.

    Public reads permit HTTP port 80 and HTTPS port 443. ``allow_local`` also
    permits private addresses and other ports, for explicitly scoped fixtures.
    Redirects receive the same checks as the original URL. Connections use the
    validated IP addresses rather than resolving the host a second time. The
    timeout is shared by DNS, connection setup, and all redirect/body reads;
    bounded text parsing also checks the deadline before returning a result.
    """

    def __init__(self, allowed_hosts: list[str], allow_local: bool = False, timeout: float = 15, max_bytes: int = 500000) -> None:
        if not allowed_hosts:
            raise WebReadError("At least one allowed host is required.")
        self.allowed_hosts = frozenset(_host_name(host) for host in allowed_hosts)
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0:
            raise WebReadError("Timeout must be a positive finite number.")
        if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes <= 0:
            raise WebReadError("The byte limit must be a positive integer.")
        self.allow_local = bool(allow_local)
        self.timeout = float(timeout)
        self.max_bytes = max_bytes

    def _normalize_url(self, url: str) -> tuple[str, str, int]:
        if not isinstance(url, str) or len(url) > 8192 or url != url.strip() or any(ord(char) < 32 or ord(char) == 127 for char in url):
            raise WebReadError("Invalid URL.")
        try:
            parsed = urlsplit(url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                raise WebReadError("Only HTTP and HTTPS URLs are supported.")
            if parsed.username is not None or parsed.password is not None:
                raise WebReadError("URLs containing credentials are not permitted.")
            host = _host_name(parsed.hostname)
            if host not in self.allowed_hosts:
                raise WebReadError("The URL host is outside the allowed scope.")
            default_port = 443 if parsed.scheme == "https" else 80
            port = parsed.port if parsed.port is not None else default_port
            if not 1 <= port <= 65535 or (not self.allow_local and port != default_port):
                raise WebReadError("The URL port is outside the allowed scope.")
            authority = f"[{host}]" if ":" in host else host
            if port != default_port:
                authority += f":{port}"
            path = quote(parsed.path or "/", safe="/:@!$&'()*+,;=-._~%")
            query = quote(parsed.query, safe="/?:@!$&'()*+,;=-._~%")
            return urlunsplit((parsed.scheme, authority, path, query, "")), host, port
        except WebReadError:
            raise
        except (ValueError, UnicodeError) as exc:
            raise WebReadError("Invalid URL.") from exc

    def _addresses(self, host: str, port: int, deadline: _FetchDeadline) -> list[str]:
        # getaddrinfo has no portable timeout. A daemon resolver may finish later,
        # but a timed-out fetch never proceeds from it to an HTTP connection.
        resolved: queue.Queue = queue.Queue(maxsize=1)

        def resolve() -> None:
            try:
                records = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP)
                resolved.put((records, None))
            except Exception as exc:
                resolved.put((None, exc))

        threading.Thread(target=resolve, daemon=True, name="SourceTrailDNS").start()
        try:
            results, error = resolved.get(timeout=deadline.remaining())
        except queue.Empty as exc:
            raise WebReadError("The page could not be read within its total time budget.") from exc
        deadline.remaining()
        if error is not None:
            raise WebReadError("The host could not be resolved.") from error
        addresses: list[str] = []
        for family, _, _, _, address in results:
            if family not in {socket.AF_INET, socket.AF_INET6}:
                continue
            try:
                resolved = ipaddress.ip_address(address[0])
            except ValueError as exc:
                raise WebReadError("The host resolved to an invalid address.") from exc
            if resolved.is_multicast or (not self.allow_local and not resolved.is_global):
                raise WebReadError("The host resolved to a non-public address.")
            if str(resolved) not in addresses:
                addresses.append(str(resolved))
        if not addresses:
            raise WebReadError("The host has no supported addresses.")
        return addresses

    def fetch(self, url: str) -> Page:
        with _FetchDeadline(self.timeout) as deadline:
            return self._fetch(url, deadline)

    def _fetch(self, url: str, deadline: _FetchDeadline) -> Page:
        started = deadline.started
        seen: set[str] = set()
        for hop in range(6):
            normalized, host, port = self._normalize_url(url)
            if normalized in seen:
                raise WebReadError("The page has a redirect loop.")
            seen.add(normalized)
            addresses = self._addresses(host, port, deadline)
            parsed = urlsplit(normalized)
            connection = _PinnedConnection(host, port, addresses, deadline.remaining(), secure=parsed.scheme == "https")
            deadline.connection = connection
            response: http.client.HTTPResponse | None = None
            try:
                target = parsed.path + ("?" + parsed.query if parsed.query else "")
                connection.request("GET", target, headers={"User-Agent": "SourceTrail/0.1", "Accept": "text/html,application/xhtml+xml,text/plain", "Accept-Encoding": "identity"})
                deadline.socket = connection.sock
                response = connection.getresponse()
                deadline.remaining()
                if response.status in {301, 302, 303, 307, 308}:
                    location = response.getheader("Location")
                    if not location:
                        raise WebReadError("The redirect has no destination.")
                    if hop == 5:
                        raise WebReadError("The page has too many redirects.")
                    url = urljoin(normalized, location)
                    continue
                if not 200 <= response.status < 300:
                    raise WebReadError(f"The server returned HTTP {response.status}.")
                content_type = response.headers.get_content_type() if response.getheader("Content-Type") else "text/plain"
                if content_type not in {"text/html", "application/xhtml+xml", "text/plain"}:
                    raise WebReadError("The page is not supported HTML or plain text.")
                if (response.getheader("Content-Encoding") or "identity").lower().strip() != "identity":
                    raise WebReadError("Compressed page responses are not supported.")
                declared_size = response.length
                chunks, received = [], 0
                while received < self.max_bytes:
                    if response.isclosed():
                        break
                    remaining = deadline.remaining()
                    if deadline.socket is not None:
                        deadline.socket.settimeout(remaining)
                    chunk = response.read1(min(65536, self.max_bytes - received))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    received += len(chunk)
                data = b"".join(chunks)
                # On some platforms watchdog shutdown makes read1 return EOF
                # rather than raise. Report the expired deadline before EOF.
                deadline.remaining()
                if declared_size is not None and received < min(declared_size, self.max_bytes):
                    raise WebReadError("The response ended before its declared content length.")
                truncated = len(data) == self.max_bytes and (declared_size is None or declared_size > self.max_bytes)
                charset = response.headers.get_content_charset() or "utf-8"
                try:
                    source = data.decode(charset, errors="replace")
                except LookupError:
                    source = data.decode("utf-8", errors="replace")
                if content_type == "text/plain":
                    blocks = [_clean_text(block) for block in re.split(r"\n\s*\n", source)]
                    blocks = [block for block in blocks if block]
                    title, raw_links, block_tags, block_tables = "", [], [""] * len(blocks), [None] * len(blocks)
                else:
                    parser = _ReadableHTML()
                    parser.feed(source)
                    parser.close()
                    title, blocks, raw_links, block_tags, block_tables = parser.title, parser.blocks, parser.links, parser.block_tags, parser.block_tables
                links: dict[str, dict[str, str]] = {}
                for link in raw_links:
                    try:
                        destination, _, _ = self._normalize_url(urljoin(normalized, link["url"].strip()))
                    except (WebReadError, ValueError, UnicodeError):
                        continue
                    if destination not in links:
                        links[destination] = {"url": destination, "label": link["label"] or destination}
                    elif not links[destination]["label"] or links[destination]["label"] == destination:
                        links[destination]["label"] = link["label"] or destination
                deadline.remaining()
                # Preserve document order and repeated headings/rows across separate tables.
                return Page(normalized, title, blocks, list(links.values()), round((time.monotonic() - started) * 1000), sha256(data).hexdigest(), content_type, truncated, block_tags, block_tables)
            except WebReadError:
                raise
            except (OSError, http.client.HTTPException, ValueError, UnicodeError) as exc:
                if isinstance(exc, TimeoutError):
                    # The socket's remaining timeout can fire just before the
                    # watchdog/event becomes observable on another thread.
                    raise WebReadError("The page could not be read within its total time budget.") from exc
                deadline.remaining()
                raise WebReadError("The page could not be read.") from exc
            finally:
                if response is not None:
                    response.close()
                connection.close()
        raise WebReadError("The page has too many redirects.")
