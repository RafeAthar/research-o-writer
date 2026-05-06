"""Local sentence embedding service.

Loads BAAI/bge-m3 (or the configured EMBEDDING_MODEL) lazily on first call.
First call will download ~2GB to the HuggingFace cache. Subsequent calls
reuse the in-process model.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING

from app.config import get_settings

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_embedder() -> "SentenceTransformer":
    from sentence_transformers import SentenceTransformer  # heavy import

    name = get_settings().embedding_model
    logger.info("loading embedding model: %s", name)
    model = SentenceTransformer(name)
    return model


def model_version() -> str:
    return f"{get_settings().embedding_model}@v1"


def embed_texts(texts: list[str], *, batch_size: int = 32) -> list[list[float]]:
    if not texts:
        return []
    model = get_embedder()
    arr = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,  # cosine == dot product when normalized
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    return arr.tolist()


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]
