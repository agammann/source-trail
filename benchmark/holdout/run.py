"""Explicit optional inference runner for the synthetic stress-development set."""

import argparse
import json
from pathlib import Path
import subprocess
import time

from benchmark.run import REPO_ROOT, build_command, score_case, summarize
from .harness import FIXTURES, load_cases, serve_fixtures


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-model", action="store_true")
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--modes", nargs="+", choices=("baseline", "verified"), default=["baseline", "verified"])
    parser.add_argument("--model", default="qwen3.5:4b-q4_K_M")
    parser.add_argument("--max-pages", type=int, default=6)
    parser.add_argument("--timeout", type=float, default=180)
    args = parser.parse_args(argv)
    if not args.run_model:
        parser.error("use --run-model for inference; test_holdout.py performs deterministic checks without a model")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    if not 1 <= args.max_pages <= 12 or args.timeout <= 0:
        parser.error("page limit must be 1 to 12 and timeout must be positive")
    cases = load_cases()
    if any(case.get("synthetic") is not True or case.get("classification") != "stress-development" for case in cases):
        parser.error("every case must retain the synthetic stress-development classification")
    cases = cases[:args.limit] if args.limit else cases
    modes = list(dict.fromkeys(args.modes))
    report = args.report_dir.resolve()
    report.mkdir(parents=True, exist_ok=True)
    scores = []
    with serve_fixtures() as base_url:
        for case in cases:
            for mode in modes:
                destination = report / mode
                destination.mkdir(exist_ok=True)
                output = destination / f"{case['id']}.json"
                if output.exists():
                    output.unlink()
                errors = []
                started = time.monotonic()
                command = build_command(case, base_url, mode, output, args.max_pages, args.model)
                try:
                    process = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=args.timeout, check=False)
                    (destination / f"{case['id']}.stdout.txt").write_text(process.stdout, encoding="utf-8")
                    (destination / f"{case['id']}.stderr.txt").write_text(process.stderr, encoding="utf-8")
                    if process.returncode:
                        errors.append(f"process_exit_code: {process.returncode}")
                except subprocess.TimeoutExpired as error:
                    for stream, value in (("stdout", error.stdout), ("stderr", error.stderr)):
                        text = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value or ""
                        (destination / f"{case['id']}.{stream}.txt").write_text(text, encoding="utf-8")
                    errors.append(f"process_timeout: {args.timeout} seconds")
                try:
                    result = json.loads(output.read_text(encoding="utf-8"))
                    if not isinstance(result, dict):
                        raise ValueError("output must be an object")
                except (OSError, ValueError) as error:
                    errors.append(f"invalid_or_missing_output: {error}")
                    result = {}
                score = score_case(case, result, base_url, FIXTURES, args.max_pages)
                score.update({"mode": mode, "classification": "stress-development", "output_path": str(output), "wall_duration_ms": round((time.monotonic() - started) * 1000)})
                if isinstance(result.get("error"), str):
                    score["application_error"] = result["error"]
                score["errors"].extend(errors)
                score["passed"] = not score["errors"]
                scores.append(score)
                (destination / f"{case['id']}.score.json").write_text(json.dumps(score, indent=2), encoding="utf-8")
                summary = summarize(scores, modes, args.max_pages, args.model)
                summary.update({"benchmark": "Source Trail synthetic stress-development", "classification": "stress-development", "scope": "Six new fictional stress cases used for development diagnosis; no held-out, broad-web, or official-challenge score claim."})
                (report / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
                print(f"{case['id']} {mode}: {'PASS' if score['passed'] else 'FAIL'}", flush=True)
    lines = ["# Synthetic stress-development results", "", "These fictional cases inform development. This is not a held-out or official challenge score.", "", "| Mode | Passed | Cases |", "| --- | --- | --- |"]
    for mode, stats in summary["by_mode"].items():
        lines.append(f"| {mode} | {stats['passed']} | {stats['cases']} |")
    lines.extend(["", f"Page limit: {args.max_pages}. Model: `{args.model}`.", "", "Resource totals and all per-case errors are in summary.json and per-case output files.", "", "## All failures", ""])
    for failure in summary["failures"]:
        cause = f"; application error: {failure['application_error']}" if failure.get("application_error") else ""
        lines.append(f"- {failure['case_id']} ({failure['mode']}): " + "; ".join(failure["errors"]) + cause)
    if not summary["failures"]:
        lines.append("No failures in this run.")
    (report / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0 if all(score["passed"] for score in scores) else 1


if __name__ == "__main__":
    raise SystemExit(main())
