"""Navigation, evidence selection, and deterministic citation validation."""

import json
import re
import time
from urllib.parse import urldefrag, urlsplit

from .model import ModelError, Ollama
from .web import WebReader, WebReadError


STOP = set("a an and are as at be by did do does for from how in is it of on or the to what when which with".split())
VERSION_MARKER = re.compile(r"(?:\bversion\s*:?\s*|\brelease\s*:?\s*|(?:^|[/\s_-])v)(\d+(?:\.\d+)*(?:[a-z][\w.+-]*|[-+][\w.+-]+)?)(?=$|[/\s,:;!?()\[\]])", re.I)


def tokens(text):
    return set(re.findall(r"[\w-]+", text.casefold())) - STOP


def versions_in(text):
    return [match.group(1).casefold() for match in VERSION_MARKER.finditer(text)]


def version_of(page):
    candidates = [urlsplit(page.url).path, page.title, " ".join(page.blocks[:3])]
    for candidate in candidates:
        markers = versions_in(candidate)
        if markers:
            return markers[0]
    return None


def same_version(actual, target):
    if not actual or not target:
        return False
    actual, target = actual.lower().lstrip("v"), str(target).lower().lstrip("v")
    return actual == target or ("." not in target and re.fullmatch(r"\d+", target) is not None
                                 and actual.startswith(target + ".") and re.fullmatch(r"\d+(?:\.\d+)*", actual) is not None)


def is_version_comparison(question):
    mentioned = set(versions_in(question))
    comparison_words = bool(re.search(r"\b(change|changed|changes|compare|compared|comparison|difference|differences|between|from|upgrade|upgrading)\b", question, re.I))
    return comparison_words and (len(mentioned) > 1 or bool(re.search(r"(?:previous|older|old)\s+version", question, re.I)))


def _windows(block, size=1800, overlap=240):
    """Overlapping exact substrings keep late facts available within the prompt cap."""
    for start in range(0, len(block), size - overlap):
        yield start, block[start:start + size]
        if start + size >= len(block):
            break


def select_evidence(pages, question, target_version=None, mode="verified", limit=24):
    query = tokens(question)
    compare = is_version_comparison(question)
    ranked = []
    for pi, page in enumerate(pages, 1):
        version = version_of(page)
        matching = same_version(version, target_version)
        if mode == "verified" and target_version and not matching and not compare:
            continue
        authority_text = " ".join([page.title] + page.blocks[:3]).lower()
        stale = bool(re.search(r"\b(withdrawn|superseded|archived|obsolete)\b", authority_text))
        preview = bool(re.search(r"\b(preview|prerelease|beta|alpha|rc|dev|nightly|snapshot)\b", authority_text)) or bool(version and re.search(r"[a-z]", version, re.I))
        explicitly_stale = bool(re.search(r"\b(withdrawn|superseded|archived|obsolete)\b", page.title, re.I))
        current_request = bool(re.search(r"\b(current|latest|stable)\b", question, re.I))
        if mode == "verified" and not compare and ((current_request and explicitly_stale)
                                                    or ("stable" in question.lower() and preview)):
            continue
        heading = page.title
        table_header = ""
        prior_was_row = False
        prior_table = None
        for bi, block in enumerate(page.blocks, 1):
            tag = page.block_tags[bi - 1] if bi <= len(page.block_tags) else ""
            if re.fullmatch(r"h[1-6]", tag):
                heading = block
            row = tag == "tr" or " | " in block or block.startswith("| ") or block.endswith(" |")
            table_id = page.block_tables[bi - 1] if bi <= len(page.block_tables) else None
            if row and (not prior_was_row or table_id != prior_table):
                table_header = block
            prior_was_row = row
            prior_table = table_id
            page_score = len(query & tokens(page.title))
            if mode == "verified":
                page_score += 10 if matching else 0
                page_score += 5 if re.search(r"\bcurrent\s+(?:stable|release)|\bstable\s+release", authority_text) else 0
                page_score -= 9 if stale else 0
                page_score -= 7 if preview and "stable" in question.lower() else 0
            for wi, (start, text) in enumerate(_windows(block), 1):
                score = len(query & tokens(text)) * 3 + page_score
                entry = {"block_id": f"P{pi}B{bi}" + (f"S{wi}" if len(block) > 1800 else ""), "url": page.url, "title": page.title,
                         "source_version": version, "section": heading, "text": text}
                if len(block) > 1800:
                    entry["text_offset"] = start
                if row and table_header != block:
                    entry["table_header"] = table_header
                ranked.append((score, pi, bi, entry))
    ranked.sort(key=lambda item: (-item[0], item[1], item[2]))
    # One bounded shared prompt; the baseline and verified variant use identical caps/model settings.
    selected, serialized_bytes = [], 0
    for _, _, _, entry in ranked:
        size = len(json.dumps(entry, ensure_ascii=False).encode("utf-8"))
        if len(selected) >= limit:
            break
        if serialized_bytes + size > 12000:
            continue
        selected.append(entry)
        serialized_bytes += size
    return selected


def validate_answer(raw, evidence, target_version=None, comparison=False, mode="verified", comparison_versions=()):
    if not isinstance(raw, dict) or not isinstance(raw.get("status"), str) or raw["status"] not in {"answered", "abstained", "conflict"}:
        raise ModelError("Response status is invalid.")
    answer, proposed = raw.get("answer"), raw.get("citations")
    if not isinstance(answer, str) or len(answer) > 1200 or not isinstance(proposed, list) or len(proposed) > 64:
        raise ModelError("Response answer or citations are invalid.")
    status = raw["status"]
    if status == "abstained":
        if answer or proposed:
            raise ModelError("An abstention must have empty answer and citations.")
        return {"status": status, "answer": "", "citations": []}
    if (status == "answered" and not answer.strip()) or (status == "conflict" and answer):
        raise ModelError("Response answer is inconsistent with its status.")
    lookup = {entry["block_id"]: entry for entry in evidence}
    citations, seen = [], set()
    for citation in proposed:
        if not isinstance(citation, dict) or not isinstance(citation.get("quote"), str) or not isinstance(citation.get("block_id"), str):
            raise ModelError("A citation is malformed.")
        entry = lookup.get(citation.get("block_id"))
        quote = citation["quote"].strip()
        if not entry or len(quote) < 4 or quote not in entry["text"]:
            raise ModelError("A cited passage is not an exact substring of the retrieved block.")
        if mode == "verified" and target_version and not comparison and not same_version(entry["source_version"], target_version):
            raise ModelError("Citation is from the wrong requested version.")
        if (entry["url"], quote) not in seen:
            seen.add((entry["url"], quote))
            citations.append({"url": entry["url"], "quote": quote, "block_id": entry["block_id"],
                              "source_version": entry["source_version"]})
    if len(citations) > 10:
        raise ModelError("The response exceeds the limit of ten distinct citations.")
    if not citations or (status == "conflict" and len(citations) < 2):
        raise ModelError("The answer does not have the required supporting sources.")
    if comparison and status == "answered":
        cited_versions = {c["source_version"] for c in citations if c["source_version"]}
        required = set(comparison_versions) | ({target_version} if target_version else set())
        if len(cited_versions) < 2 or any(not any(same_version(actual, requested) for actual in cited_versions) for requested in required):
            raise ModelError("A version comparison must cite every requested version and at least two identifiable versions.")
    return {"status": status, "answer": answer.strip(), "citations": citations}


def query(question, urls, target_version=None, mode="verified", max_pages=6, allow_local=False, model=None):
    started = time.monotonic()
    if not isinstance(question, str) or not question.strip() or len(question) > 2000:
        raise ValueError("Provide a question of 1 to 2000 characters.")
    if not isinstance(mode, str) or mode not in {"verified", "baseline"} or not isinstance(max_pages, int) or isinstance(max_pages, bool) or not 1 <= max_pages <= 12:
        raise ValueError("Choose a valid mode and a page budget of 1 to 12.")
    if target_version is not None and (not isinstance(target_version, str) or len(target_version) > 40):
        raise ValueError("Target version must be text of at most 40 characters.")
    if target_version is not None:
        target_version = target_version.strip() or None
    if not isinstance(urls, list) or not 1 <= len(urls) <= max_pages or not all(isinstance(u, str) and len(u) <= 2048 for u in urls):
        raise ValueError("Provide one or more starting URLs within the page budget.")
    hosts = list({urlsplit(u).hostname for u in urls})
    if None in hosts:
        raise ValueError("Starting URLs must be absolute HTTP(S) addresses.")
    reader = WebReader(hosts, allow_local=allow_local, timeout=12)
    queue = [(10000 - i, urldefrag(url)[0]) for i, url in enumerate(urls)]
    pages, visited, trace = [], set(), []
    attempts = 0
    # Bound attempted reads, including failures; failure never silently expands the budget.
    while queue and attempts < max_pages:
        queue.sort(key=lambda item: -item[0])
        _, url = queue.pop(0)
        if url in visited:
            continue
        if time.monotonic() - started > 75:
            trace.append({"action": "stop", "reason": "navigation time budget reached"})
            break
        visited.add(url)
        attempts += 1
        reader.timeout = min(12, max(0.1, 75 - (time.monotonic() - started)))
        try:
            page = reader.fetch(url)
            pages.append(page)
            trace.append({"action": "read", "url": page.url, "title": page.title,
                          "blocks": len(page.blocks), "elapsed_ms": page.elapsed_ms,
                          "sha256": page.sha256, "truncated": page.truncated})
            known = visited | {item[1] for item in queue}
            for link in page.links:
                destination = urldefrag(link["url"])[0]
                if destination not in known:
                    priority = len(tokens(question) & tokens(link["label"] + " " + destination)) * 3
                    # Identical traversal in both modes: comparison isolates evidence selection.
                    if target_version and re.search(r"(?:[/_-]v|\bversion\s*)" + re.escape(str(target_version)) + r"(?:[/.\s_-]|$)", destination + " " + link["label"], re.I):
                        priority += 5
                    queue.append((priority, destination))
                    known.add(destination)
        except WebReadError as exc:
            trace.append({"action": "read_failed", "url": url, "reason": str(exc)})
    evidence = select_evidence(pages, question, target_version, mode)
    comparison = is_version_comparison(question)
    metrics = {"pages": attempts, "successful_pages": len(pages), "model_calls": 0, "input_tokens": 0, "output_tokens": 0}
    result = {"question": question, "requested_version": target_version, "mode": mode,
              "sources": [{"url": p.url, "title": p.title, "version": version_of(p)} for p in pages],
              "evidence": evidence, "trace": trace, "metrics": metrics}
    if not pages:
        result.update({"status": "failed", "answer": "", "citations": [],
                       "error": "None of the scoped sources could be read."})
    elif not evidence:
        result.update({"status": "abstained", "answer": "", "citations": []})
    else:
        try:
            metrics["model_calls"] = 1
            metrics["input_tokens"] = metrics["output_tokens"] = None
            metrics["usage_recorded"] = False
            raw, use = (model or Ollama()).answer(question, evidence, target_version)
            metrics.update(use)
            metrics["usage_recorded"] = use.get("usage_recorded", all(isinstance(use.get(key), int) and not isinstance(use[key], bool) for key in ("input_tokens", "output_tokens")))
            versions = versions_in(question)
            result.update(validate_answer(raw, evidence, target_version, comparison, mode, versions))
        except ModelError as exc:
            result.update({"status": "failed", "answer": "", "citations": [], "error": str(exc)})
    metrics["duration_ms"] = round((time.monotonic() - started) * 1000)
    return result
