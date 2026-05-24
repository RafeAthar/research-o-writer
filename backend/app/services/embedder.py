"""Sentence embedding service with a pluggable backend.

EMBEDDING_PROVIDER selects the backend:
  - "local"  (default): BAAI/bge-m3 (or EMBEDDING_MODEL) loaded in-process.
               First call downloads ~2GB to the HuggingFace cache; no network
               at query time after that.
  - "voyage":           Voyage AI API (VOYAGE_EMBEDDING_MODEL, default voyage-4
               at 1024 dims). No local model / no torch RAM; text is sent to
               Voyage. Requires VOYAGE_API_KEY.

Both produce unit-normalized 1024-dim vectors, so they're interchangeable at
the pgvector-column level — but their vector spaces differ, so switching
providers requires re-embedding existing sources.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING

from app.config import get_settings

if TYPE_CHECKING:
    import voyageai
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


@lru_cache(maxsize=1)
def _voyage_client() -> voyageai.Client:
    import voyageai

    s = get_settings()
    if not s.voyage_api_key:
        raise RuntimeError("EMBEDDING_PROVIDER=voyage requires VOYAGE_API_KEY")
    return voyageai.Client(api_key=s.voyage_api_key)


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
    client = _voyage_client()
    out: list[list[float]] = []
    for i in range(0, len(texts), _VOYAGE_BATCH):
        batch = texts[i : i + _VOYAGE_BATCH]
        resp = client.embed(
            batch,
            model=s.voyage_embedding_model,
            input_type=input_type,
            # None = the model's native dimension. voyage-3 is fixed at 1024
            # (and rejects output_dimension); 3.5/large/4 default to 1024 too,
            # so both match our pgvector column without forcing it.
            output_dimension=s.voyage_output_dimension,
        )
        out.extend(resp.embeddings)
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
