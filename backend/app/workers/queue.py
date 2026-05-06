from __future__ import annotations

from functools import lru_cache

from redis import Redis
from rq import Queue

from app.config import get_settings


@lru_cache
def get_redis() -> Redis:
    s = get_settings()
    return Redis(host=s.redis_host, port=s.redis_port, decode_responses=False)


@lru_cache
def get_queue(name: str = "ingest") -> Queue:
    return Queue(name, connection=get_redis())
