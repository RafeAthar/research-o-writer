"""CLI: ``python -m app.eval.run --file eval_data/eval_set.json [--k 10] [--with-chat]``"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.eval.runner import run_eval_sync
from app.eval.schema import EvalEntry


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Research-o-Writer eval set.")
    parser.add_argument(
        "--file",
        type=Path,
        default=Path("eval_data/eval_set.json"),
        help="path to the eval set JSON (relative to backend/)",
    )
    parser.add_argument("--k", type=int, default=10, help="top-K to score against")
    parser.add_argument(
        "--with-chat",
        action="store_true",
        help="also run chat completions; requires ANTHROPIC_API_KEY",
    )
    parser.add_argument(
        "--ids",
        nargs="*",
        default=None,
        help="restrict to specific entry ids (default: all)",
    )
    args = parser.parse_args()

    path: Path = args.file
    if not path.exists():
        print(f"eval set not found: {path}", file=sys.stderr)
        return 2
    payload = json.loads(path.read_text())
    raw_entries = payload.get("entries") if isinstance(payload, dict) else payload
    if not isinstance(raw_entries, list):
        print("eval file must contain a list, or {entries:[...]}", file=sys.stderr)
        return 2

    entries = [EvalEntry.from_dict(e) for e in raw_entries]
    if args.ids:
        wanted = set(args.ids)
        entries = [e for e in entries if e.id in wanted]
        if not entries:
            print("no eval entries matched --ids", file=sys.stderr)
            return 2

    report = run_eval_sync(entries, k=args.k, with_chat=args.with_chat)
    print(report.summary())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
