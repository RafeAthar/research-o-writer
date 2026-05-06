"""Upload the synthetic eval articles to a running Research-o-Writer backend.

Usage (run from the ``backend/`` directory):

    python scripts/upload_eval_articles.py --wait

Environment variables:
    APP_BASE_URL    default http://localhost:8000
    APP_AUTH_TOKEN  default dev-token  (must match Settings.app_auth_token)

The script is idempotent: re-uploading the same file is a no-op because the
``/api/v1/sources`` endpoint deduplicates by sha256.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import httpx

DEFAULT_ARTICLES_DIR = Path(__file__).resolve().parents[1] / "eval_data" / "articles"


def _base_url() -> str:
    return os.environ.get("APP_BASE_URL", "http://localhost:8000").rstrip("/")


def _token() -> str:
    return os.environ.get("APP_AUTH_TOKEN", "dev-token")


def _headers() -> dict[str, str]:
    return {"X-Auth-Token": _token()}


def upload_one(path: Path) -> int:
    url = f"{_base_url()}/api/v1/sources"
    title = path.stem.replace("_", " ").title()
    # Use the H1 as the title if present; the parser still re-titles things,
    # but a sensible Source.title makes the eval set's expected_source_title
    # work without further wiring.
    first = path.read_text(encoding="utf-8").splitlines()[0]
    if first.startswith("# "):
        title = first[2:].strip()
    with path.open("rb") as f:
        resp = httpx.post(
            url,
            headers=_headers(),
            files={"file": (path.name, f, "text/markdown")},
            data={"title": title},
            timeout=60,
        )
    resp.raise_for_status()
    body = resp.json()
    print(f"  uploaded id={body['id']:<4} status={body['status']:<10} {title}")
    return int(body["id"])


def list_sources() -> list[dict]:
    resp = httpx.get(f"{_base_url()}/api/v1/sources", headers=_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


def wait_until_ready(ids: list[int], *, timeout_s: int = 600) -> None:
    deadline = time.time() + timeout_s
    pending = set(ids)
    while pending and time.time() < deadline:
        rows = {r["id"]: r for r in list_sources()}
        for sid in list(pending):
            r = rows.get(sid)
            if not r:
                pending.discard(sid)
                continue
            if r["status"] == "ready":
                print(f"  ready: id={sid} {r['title']}")
                pending.discard(sid)
            elif r["status"] == "failed":
                print(f"  FAILED: id={sid} {r['title']} :: {r.get('ingestion_error')}")
                pending.discard(sid)
        if pending:
            time.sleep(2)
    if pending:
        print(f"timeout waiting for: {sorted(pending)}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dir",
        type=Path,
        default=DEFAULT_ARTICLES_DIR,
        help="directory containing the article files",
    )
    parser.add_argument(
        "--wait",
        action="store_true",
        help="poll /sources until each uploaded source reaches status=ready",
    )
    args = parser.parse_args()

    if not args.dir.exists():
        print(f"articles dir not found: {args.dir}", file=sys.stderr)
        return 2

    print(f"uploading from {args.dir} -> {_base_url()}")
    files = sorted(p for p in args.dir.iterdir() if p.is_file())
    ids: list[int] = []
    for path in files:
        ids.append(upload_one(path))

    if args.wait:
        print("waiting for ingestion to finish...")
        wait_until_ready(ids)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
