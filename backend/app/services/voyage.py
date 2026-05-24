"""Minimal Voyage AI REST client.

We call the HTTP API directly with httpx instead of the official `voyageai`
SDK: the SDK caps at Python <3.14, and the REST surface we need (embeddings +
rerank) is tiny. Shared by embedder.py and reranker.py.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import httpx

from app.config import get_settings

_BASE_URL = "https://api.voyageai.com/v1"


@lru_cache(maxsize=1)
def _client() -> httpx.Client:
    return httpx.Client(base_url=_BASE_URL, timeout=60.0)


def voyage_post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    s = get_settings()
    if not s.voyage_api_key:
        raise RuntimeError("Voyage provider selected but VOYAGE_API_KEY is unset")
    resp = _client().post(
        path,
        headers={"Authorization": f"Bearer {s.voyage_api_key}"},
        json=payload,
    )
    resp.raise_for_status()
    return resp.json()
