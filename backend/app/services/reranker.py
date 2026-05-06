"""Local cross-encoder reranker.

Uses BAAI/bge-reranker-v2-m3 by default. First call downloads the model.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING

from app.config import get_settings

if TYPE_CHECKING:
    from sentence_transformers import CrossEncoder

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_reranker() -> "CrossEncoder":
    from sentence_transformers import CrossEncoder  # heavy import

    name = get_settings().reranker_model
    logger.info("loading reranker model: %s", name)
    return CrossEncoder(name)


def rerank(query: str, candidates: list[tuple[int, str]]) -> list[tuple[int, float]]:
    """Score (chunk_id, text) pairs against a query. Returns sorted desc."""
    if not candidates:
        return []
    model = get_reranker()
    pairs = [(query, text) for _id, text in candidates]
    scores = model.predict(pairs, show_progress_bar=False)
    out = list(zip([cid for cid, _ in candidates], (float(s) for s in scores), strict=False))
    out.sort(key=lambda x: x[1], reverse=True)
    return out
