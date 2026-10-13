import argparse
import json
from pathlib import Path
import sys

from .engine import query
from .model import Ollama


def main():
    parser = argparse.ArgumentParser(description="Source Trail: web answers with exact supporting passages.")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("query", help="Retrieve sources and answer one question.")
    run.add_argument("--question", required=True)
    run.add_argument("--url", action="append", required=True, help="Starting URL. Repeat for multiple starting pages.")
    run.add_argument("--target-version")
    run.add_argument("--mode", choices=["verified", "baseline"], default="verified")
    run.add_argument("--max-pages", type=int, default=6)
    run.add_argument("--output", type=Path)
    run.add_argument("--model")
    run.add_argument("--allow-local", action="store_true", help="Explicitly permit local benchmark fixtures.")
    serve = sub.add_parser("serve", help="Start the local evidence inspector.")
    serve.add_argument("--host", default="127.0.0.1", choices=["127.0.0.1", "localhost"])
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--allow-local", action="store_true", help="Permit local fixture sources for development.")
    args = parser.parse_args()
    if args.command == "serve":
        from .server import serve as start
        start(args.host, args.port, args.allow_local)
        return 0
    try:
        result = query(args.question, args.url, args.target_version, args.mode, args.max_pages,
                       args.allow_local, Ollama(model=args.model))
    except ValueError as exc:
        parser.error(str(exc))
    encoded = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(encoded)
    return 1 if result["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
