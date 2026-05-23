"""Entrypoint to launch an RQ worker:  python -m app.workers.run_worker [queues...]

On macOS the default RQ worker (which forks a work-horse per job) crashes when
the job touches Objective-C-backed libraries like torch/sentence-transformers
("+[NSNumber initialize] may have been in progress ... fork() was called").
We avoid the fork there by using SimpleWorker, which runs jobs in-process.
Override with RQ_WORKER_CLASS=fork|simple if needed.
"""

from __future__ import annotations

import os
import sys

# Belt-and-suspenders for any remaining fork on macOS; must be set before the
# Objective-C frameworks initialise.
os.environ.setdefault("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")

from rq import SimpleWorker, Worker  # noqa: E402

from app.workers.queue import get_redis  # noqa: E402


def _worker_class() -> type[Worker]:
    choice = os.environ.get("RQ_WORKER_CLASS", "").lower()
    if choice == "fork":
        return Worker
    if choice == "simple":
        return SimpleWorker
    # Default: no-fork on macOS, normal forking worker elsewhere.
    return SimpleWorker if sys.platform == "darwin" else Worker


def main() -> None:
    queues = sys.argv[1:] or ["ingest", "embed"]
    worker_cls = _worker_class()
    worker_cls(queues, connection=get_redis()).work(with_scheduler=True)


if __name__ == "__main__":
    main()
