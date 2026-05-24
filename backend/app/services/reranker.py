"""Reranker with a pluggable backend.

RERANKER_PROVIDER selects the backend:
  - "off" (default):   Skip reranking; preserve the caller's input order.
  - "local":           BAAI/bge-reranker-v2-m3 cross-encoder, loaded in-process
              (~2GB RAM). First call downloads the model.
  - "voyage":          Voyage AI rerank REST API (VOYAGE_RERANKER_MODEL, default
              rerank-2.5). No local model; candidate text is sent to Voyage.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING

from app.config import get_settings
from app.services.voyage import voyage_post

if TYPE_CHECKING:
    from sentence_transformers import CrossEncoder

logger = logging.getLogger(__name__)


def _provider() -> str:
    return get_settings().reranker_provider.strip().lower()


@lru_cache(maxsize=1)
def get_reranker() -> CrossEncoder:
    from sentence_transformers import CrossEncoder  # heavy import

    name = get_settings().reranker_model
    logger.info("loading reranker model: %s", name)
    return CrossEncoder(name)


def _rerank_local(query: str, candidates: list[tuple[int, str]]) -> list[tuple[int, float]]:
    model = get_reranker()
    pairs = [(query, text) for _id, text in candidates]
    scores = model.predict(pairs, show_progress_bar=False)
    out = list(zip([cid for cid, _ in candidates], (float(s) for s in scores), strict=False))
    out.sort(key=lambda x: x[1], reverse=True)
    return out


def _rerank_voyage(query: str, candidates: list[tuple[int, str]]) -> list[tuple[int, float]]:
    s = get_settings()
    docs = [text for _id, text in candidates]
    payload = {"query": query, "documents": docs, "model": s.voyage_reranker_model}
    data = voyage_post("/rerank", payload)["data"]
    # each result carries "index" (into docs) and "relevance_score", sorted desc.
    return [(candidates[r["index"]][0], float(r["relevance_score"])) for r in data]


def rerank(query: str, candidates: list[tuple[int, str]]) -> list[tuple[int, float]]:
    """Score (chunk_id, text) pairs against a query. Returns sorted desc."""
    if not candidates:
        return []
    provider = _provider()
    if provider == "off":
        # Keep input order with descending synthetic scores.
        n = len(candidates)
        return [(cid, float(n - i)) for i, (cid, _) in enumerate(candidates)]
    if provider == "voyage":
        return _rerank_voyage(query, candidates)
    return _rerank_local(query, candidates)
