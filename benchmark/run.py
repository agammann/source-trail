"""Run Source Trail against explicitly synthetic, fictional loopback pages.

Ground truth stays in the evaluator. Each app invocation receives only its
question, starting URL, requested version (if any), and ordinary CLI options.
The answer matcher is an alias check, not a semantic or independent human judge.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from functools import partial
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import re
import subprocess
import sys
from threading import Thread
import time
import unicodedata
from urllib.parse import unquote, urljoin, urlsplit


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
STATUSES = {"answered", "abstained", "conflict", "failed"}


def normalized_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).split())


def answer_tokens(value: str) -> list[str]:
    return re.findall(r"\w+", unicodedata.normalize("NFKC", value).casefold())


def answer_matches(answer: str, aliases: list[str]) -> bool:
    """Match the entire normalized token sequence to one explicit alias."""
    actual = answer_tokens(answer)
    for alias in aliases:
        expected = answer_tokens(alias)
        if expected and actual == expected:
            return True
    return False


class VisibleTextParser(HTMLParser):
    """Get whitespace-normalized visible text from simple fixture HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.stack: list[tuple[str, bool]] = []
        self.row_has_cell = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        style = re.sub(r"\s+", "", (attributes.get("style") or "").casefold())
        blocked = (
            bool(self.stack and self.stack[-1][1])
            or tag in {"head", "script", "style", "noscript", "template", "svg"}
            or "hidden" in attributes
            or (attributes.get("aria-hidden") or "").casefold() == "true"
            or re.search(r"(?:^|;)(?:display:none|visibility:hidden)(?:!important)?(?:;|$)", style) is not None
        )
        if not blocked:
            if tag == "tr":
                self.row_has_cell = False
            if tag in {"td", "th"}:
                self.parts.append(" | " if self.row_has_cell else " ")
                self.row_has_cell = True
            else:
                self.parts.append(" ")
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append((tag, blocked))

    def handle_endtag(self, tag: str) -> None:
        matching = next((index for index in range(len(self.stack) - 1, -1, -1) if self.stack[index][0] == tag), None)
        if matching is None:
            return
        if not self.stack[matching][1]:
            self.parts.append(" ")
        del self.stack[matching:]

    def handle_data(self, data: str) -> None:
        if not (self.stack and self.stack[-1][1]):
            self.parts.append(data)


def visible_text(path: Path) -> str:
    parser = VisibleTextParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return normalized_text("".join(parser.parts))


def citation_path(url: str, base_url: str) -> str | None:
    parsed = urlsplit(url)
    base = urlsplit(base_url)
    if parsed.scheme != base.scheme or parsed.netloc != base.netloc:
        return None
    return unquote(parsed.path)


def fixture_file(path: str, fixture_root: Path) -> Path | None:
    candidate = (fixture_root / path.lstrip("/")).resolve()
    try:
        candidate.relative_to(fixture_root.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def score_case(
    case: dict,
    result: dict,
    base_url: str,
    fixture_root: Path = HERE / "fixtures",
    max_pages: int = 6,
) -> dict:
    """Validate app output and score status, aliases, exact sources, quotes."""
    errors: list[str] = []
    expected_status = case["expected_status"]
    status = result.get("status")
    status_match = status == expected_status
    if status not in STATUSES:
        errors.append("invalid_status")
    if not status_match:
        errors.append(f"status_mismatch: expected {expected_status}, got {status!r}")
    answer = result.get("answer")
    if not isinstance(answer, str):
        errors.append("answer_must_be_a_string")
        answer = ""
    aliases = [case.get("expected_answer", ""), *case.get("answer_aliases", [])]
    answer_match = expected_status != "answered" or answer_matches(answer, aliases)
    if not answer_match:
        errors.append("answer_alias_mismatch")

    citations = result.get("citations")
    if not isinstance(citations, list):
        errors.append("citations_must_be_a_list")
        citations = []
    actual_sources: set[str] = set()
    invalid_quotes: list[int] = []
    for index, citation in enumerate(citations):
        if not isinstance(citation, dict):
            errors.append(f"citation_{index}_must_be_an_object")
            invalid_quotes.append(index)
            continue
        url = citation.get("url")
        quote = citation.get("quote")
        block_id = citation.get("block_id")
        source_version = citation.get("source_version")
        if not isinstance(block_id, str) or not block_id.strip():
            errors.append(f"citation_{index}_missing_block_id")
        if "source_version" not in citation or (
            source_version is not None and not isinstance(source_version, str)
        ):
            errors.append(f"citation_{index}_invalid_source_version")
        path = citation_path(url, base_url) if isinstance(url, str) else None
        if path is not None:
            actual_sources.add(path)
        source_file = fixture_file(path, fixture_root) if path is not None else None
        if (
            source_file is None
            or not isinstance(quote, str)
            or not normalized_text(quote)
            or normalized_text(quote) not in visible_text(source_file)
        ):
            invalid_quotes.append(index)
            errors.append(f"citation_{index}_quote_not_in_visible_source")
    expected_sources = set(case["expected_source_paths"])
    source_match = actual_sources == expected_sources
    if not source_match:
        errors.append(
            "source_set_mismatch: "
            f"missing={sorted(expected_sources - actual_sources)}, "
            f"extra={sorted(actual_sources - expected_sources)}"
        )

    metrics = result.get("metrics")
    if not isinstance(metrics, dict):
        errors.append("metrics_must_be_an_object")
        metrics = {}
    for name in ("pages", "model_calls", "input_tokens", "output_tokens", "duration_ms"):
        value = metrics.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            errors.append(f"metric_{name}_must_be_a_nonnegative_number")
        elif name != "duration_ms" and not isinstance(value, int):
            errors.append(f"metric_{name}_must_be_an_integer")
    pages = metrics.get("pages")
    page_budget_met = isinstance(pages, int) and not isinstance(pages, bool) and 0 <= pages <= max_pages
    if not page_budget_met:
        errors.append(f"page_budget_exceeded_or_missing: limit={max_pages}, actual={pages!r}")
    if not isinstance(result.get("trace"), list):
        errors.append("trace_must_be_a_list")
    return {
        "case_id": case["id"],
        "synthetic": True,
        "status_match": status_match,
        "answer_match": answer_match,
        "source_match": source_match,
        "valid_quotes": not invalid_quotes,
        "invalid_quote_indices": invalid_quotes,
        "page_budget_met": page_budget_met,
        "actual_source_paths": sorted(actual_sources),
        "expected_source_paths": sorted(expected_sources),
        "metrics": metrics,
        "passed": not errors,
        "errors": errors,
    }


class QuietFixtureHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


@contextmanager
def fixture_server(fixture_root: Path = HERE / "fixtures"):
    handler = partial(QuietFixtureHandler, directory=str(fixture_root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server.daemon_threads = True
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/"
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


def build_command(
    case: dict,
    base_url: str,
    mode: str,
    output: Path,
    max_pages: int,
    model: str,
) -> list[str]:
    command = [
        sys.executable, "-m", "sourcetrail", "query",
        "--question", case["question"],
        "--url", urljoin(base_url, case["start_path"]),
        "--mode", mode,
        "--max-pages", str(max_pages),
        "--allow-local",
        "--output", str(output),
        "--model", model,
    ]
    if case.get("target_version"):
        command.extend(["--target-version", case["target_version"]])
    return command


def summarize(scores: list[dict], modes: list[str], max_pages: int, model: str) -> dict:
    by_mode: dict[str, dict] = {}
    for mode in modes:
        selected = [score for score in scores if score["mode"] == mode]
        totals = {
            name: sum(
                score["metrics"].get(name, 0)
                for score in selected
                if isinstance(score["metrics"].get(name), (int, float))
                and not isinstance(score["metrics"].get(name), bool)
                and math.isfinite(score["metrics"][name])
            )
            for name in ("pages", "model_calls", "input_tokens", "output_tokens", "duration_ms")
        }
        by_mode[mode] = {
            "cases": len(selected),
            "passed": sum(score["passed"] for score in selected),
            "status_correct": sum(score["status_match"] for score in selected),
            "answer_alias_correct": sum(score["answer_match"] for score in selected),
            "exact_sources_correct": sum(score["source_match"] for score in selected),
            "quotes_valid": sum(score["valid_quotes"] for score in selected),
            "within_page_budget": sum(score["page_budget_met"] for score in selected),
            "totals": totals,
        }
    return {
        "benchmark": "Source Trail synthetic fixtures",
        "synthetic": True,
        "scope": "Hand-authored fictional pages; not the official challenge evaluator.",
        "answer_scoring": "Exact full normalized token sequence against explicit aliases; no semantic judge.",
        "citation_scoring": "Exact necessary source path set and quote presence in visible fixture text. Block IDs are shape-checked only.",
        "model": model,
        "page_limit_per_query": max_pages,
        "by_mode": by_mode,
        "failures": [score for score in scores if not score["passed"]],
        "cases": scores,
    }


def write_report(report_dir: Path, summary: dict) -> None:
    (report_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    lines = [
        "# Source Trail synthetic fixture results", "",
        "All pages and facts in this benchmark are fictional. This is a local engineering check, not an official challenge score.", "",
        f"Model: `{summary['model']}`. Page limit: {summary['page_limit_per_query']} per query.", "",
        "Answers must equal a full hand-authored alias after token normalization; no semantic judge is used. Sources must match the exact necessary path set. Quotes must occur in visible fixture text; block IDs are shape-checked only.", "",
        "| Mode | Passed | Status | Answer aliases | Exact sources | Quotes | Page budget |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for mode, stats in summary["by_mode"].items():
        total = stats["cases"]
        fields = ["passed", "status_correct", "answer_alias_correct", "exact_sources_correct", "quotes_valid", "within_page_budget"]
        lines.append("| " + mode + " | " + " | ".join(f"{stats[field]}/{total}" for field in fields) + " |")
    lines.extend(["", "## Recorded resource use", "", "| Mode | Pages | Model calls | Input tokens | Output tokens | Duration ms |", "| --- | --- | --- | --- | --- | --- |"])
    for mode, stats in summary["by_mode"].items():
        lines.append("| " + mode + " | " + " | ".join(str(value) for value in stats["totals"].values()) + " |")
    lines.extend(["", "## All failures", ""])
    if not summary["failures"]:
        lines.append("No failures in this run.")
    for failure in summary["failures"]:
        lines.append(f"- `{failure['case_id']}` ({failure['mode']}): " + "; ".join(failure["errors"]))
    (report_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--modes", nargs="+", choices=("baseline", "verified"), default=["baseline", "verified"])
    parser.add_argument("--max-pages", type=int, default=6)
    parser.add_argument("--model", default="qwen3.5:4b-q4_K_M")
    parser.add_argument("--timeout", type=float, default=180)
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    if args.max_pages < 1 or args.timeout <= 0:
        parser.error("page limit and timeout must be positive")
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    if not isinstance(cases, list) or any(case.get("synthetic") is not True for case in cases):
        parser.error("every fixture case must be explicitly synthetic")
    cases = cases[: args.limit] if args.limit else cases
    modes = list(dict.fromkeys(args.modes))
    report_dir = args.report_dir.resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    scores: list[dict] = []
    with fixture_server() as base_url:
        for case in cases:
            for mode in modes:
                mode_dir = report_dir / mode
                mode_dir.mkdir(exist_ok=True)
                output = mode_dir / f"{case['id']}.json"
                if output.exists():
                    output.unlink()
                command = build_command(case, base_url, mode, output, args.max_pages, args.model)
                execution_errors: list[str] = []
                started = time.monotonic()
                try:
                    completed = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=args.timeout, check=False)
                    (mode_dir / f"{case['id']}.stdout.txt").write_text(completed.stdout, encoding="utf-8")
                    (mode_dir / f"{case['id']}.stderr.txt").write_text(completed.stderr, encoding="utf-8")
                    if completed.returncode:
                        execution_errors.append(f"process_exit_code: {completed.returncode}")
                except subprocess.TimeoutExpired as error:
                    for name, value in (("stdout", error.stdout), ("stderr", error.stderr)):
                        text = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value or ""
                        (mode_dir / f"{case['id']}.{name}.txt").write_text(text, encoding="utf-8")
                    execution_errors.append(f"process_timeout: {args.timeout} seconds")
                try:
                    result = json.loads(output.read_text(encoding="utf-8"))
                    if not isinstance(result, dict):
                        raise ValueError("output must be a JSON object")
                except (OSError, ValueError) as error:
                    execution_errors.append(f"invalid_or_missing_output: {error}")
                    result = {}
                score = score_case(case, result, base_url, max_pages=args.max_pages)
                score.update({"mode": mode, "output_path": str(output), "wall_duration_ms": round((time.monotonic() - started) * 1000)})
                score["errors"].extend(execution_errors)
                score["passed"] = not score["errors"]
                (mode_dir / f"{case['id']}.score.json").write_text(json.dumps(score, indent=2), encoding="utf-8")
                scores.append(score)
                summary = summarize(scores, modes, args.max_pages, args.model)
                write_report(report_dir, summary)
                print(f"{case['id']} {mode}: {'PASS' if score['passed'] else 'FAIL'}", flush=True)
    print(f"Synthetic results saved to {report_dir}", flush=True)
    return 0 if all(score["passed"] for score in scores) else 1


if __name__ == "__main__":
    raise SystemExit(main())
