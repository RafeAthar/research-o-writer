"""Entrypoint to launch an RQ worker:  python -m app.workers.run_worker [queues...]"""

from __future__ import annotations

import sys

from rq import Worker

from app.workers.queue import get_redis


def main() -> None:
    queues = sys.argv[1:] or ["ingest", "embed"]
    Worker(queues, connection=get_redis()).work(with_scheduler=True)


if __name__ == "__main__":
    main()
