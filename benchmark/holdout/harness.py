"""Loopback retrieval and evidence probes; no model or external network calls."""

import json
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from benchmark.run import fixture_server
from sourcetrail.engine import select_evidence
from sourcetrail.web import WebReader


HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"


def load_cases():
    return json.loads((HERE / "cases.json").read_text(encoding="utf-8"))


def fetch_case(case, base_url, max_pages=6):
    """Retrieve only the supplied start URL and its scoped links, no ground truth."""
    reader = WebReader([urlsplit(base_url).hostname], allow_local=True)
    queue = [urljoin(base_url, case["start_path"])]
    visited, pages = set(), []
    while queue and len(visited) < max_pages:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        page = reader.fetch(url)
        pages.append(page)
        for link in page.links:
            if link["url"] not in visited and link["url"] not in queue:
                queue.append(link["url"])
    return pages


def evidence_for(case, pages, mode="verified"):
    # Expected answers, quotes, source sets, and diagnostic facts are not passed.
    return select_evidence(pages, case["question"], case.get("target_version"), mode)


def serve_fixtures():
    return fixture_server(FIXTURES)
