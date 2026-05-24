"""Sentence embedding service with a pluggable backend.

EMBEDDING_PROVIDER selects the backend:
  - "voyage" (default): Voyage AI REST API (VOYAGE_EMBEDDING_MODEL, default
               voyage-3 at 1024 dims). No local model / no torch RAM; text is
               sent to Voyage. Requires VOYAGE_API_KEY.
  - "local":            BAAI/bge-m3 (or EMBEDDING_MODEL) loaded in-process.
               First call downloads ~2GB to the HuggingFace cache; no network
               at query time after that.

Both produce unit-normalized 1024-dim vectors, so they're interchangeable at
the pgvector-column level — but their vector spaces differ, so switching
providers requires re-embedding existing sources.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING

from app.config import get_settings
from app.services.voyage import voyage_post

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Voyage caps each request by texts and tokens; keep batches conservative since
# book chunks can be several hundred tokens each.
_VOYAGE_BATCH = 128


def _provider() -> str:
    return get_settings().embedding_provider.strip().lower()


@lru_cache(maxsize=1)
def get_embedder() -> SentenceTransformer:
    from sentence_transformers import SentenceTransformer  # heavy import

    name = get_settings().embedding_model
    logger.info("loading embedding model: %s", name)
    return SentenceTransformer(name)


def model_version() -> str:
    s = get_settings()
    if _provider() == "voyage":
        return f"{s.voyage_embedding_model}@v1"
    return f"{s.embedding_model}@v1"


def _embed_local(texts: list[str], batch_size: int) -> list[list[float]]:
    model = get_embedder()
    arr = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,  # cosine == dot product when normalized
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    return arr.tolist()


def _embed_voyage(texts: list[str], input_type: str) -> list[list[float]]:
    s = get_settings()
    out: list[list[float]] = []
    for i in range(0, len(texts), _VOYAGE_BATCH):
        batch = texts[i : i + _VOYAGE_BATCH]
        payload: dict = {
            "input": batch,
            "model": s.voyage_embedding_model,
            "input_type": input_type,
        }
        # Only send output_dimension when explicitly set: voyage-3 is fixed at
        # 1024 and rejects the field; 3.5/large/4 default to 1024 too, so both
        # match our pgvector column without forcing it.
        if s.voyage_output_dimension is not None:
            payload["output_dimension"] = s.voyage_output_dimension
        data = voyage_post("/embeddings", payload)["data"]
        data.sort(key=lambda d: d["index"])  # preserve input order
        out.extend(d["embedding"] for d in data)
    return out


def embed_texts(texts: list[str], *, batch_size: int = 32) -> list[list[float]]:
    if not texts:
        return []
    if _provider() == "voyage":
        return _embed_voyage(texts, "document")
    return _embed_local(texts, batch_size)


def embed_query(text: str) -> list[float]:
    if _provider() == "voyage":
        return _embed_voyage([text], "query")[0]
    return _embed_local([text], 32)[0]
