"""Embedding worker. Runs in an RQ worker process.

For a given source_id, embeds all chunks that don't yet have a vector,
in batches, and stores the result on chunks.embedding plus the model
version on chunks.embedding_model_version.
"""

from __future__ import annotations

import logging

from sqlalchemy import select, update
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.models.source import Chunk, Source, SourceStatus
from app.services.embedder import embed_texts, model_version
from app.workers.ingest import _set_status, _sync_engine

logger = logging.getLogger(__name__)


def _batched(items: list, n: int):
    for i in range(0, len(items), n):
        yield items[i : i + n]


def embed_source(source_id: int, batch_size: int = 32) -> None:
    Engine = _sync_engine()
    SF = sessionmaker(bind=Engine, expire_on_commit=False)

    with SF() as db:
        try:
            chunks = (
                db.execute(
                    select(Chunk).where(Chunk.source_id == source_id, Chunk.embedding.is_(None))
                )
                .scalars()
                .all()
            )
            if not chunks:
                _set_status(db, source_id, SourceStatus.READY)
                return

            mv = model_version()
            for batch in _batched(chunks, batch_size):
                texts = [c.text for c in batch]
                embeddings = embed_texts(texts)
                for c, vec in zip(batch, embeddings, strict=True):
                    c.embedding = vec
                    c.embedding_model_version = mv
                db.commit()

            _set_status(db, source_id, SourceStatus.READY)

        except Exception as e:
            logger.exception("embedding failed for source %s", source_id)
            _set_status(db, source_id, SourceStatus.FAILED, error=f"embed: {e}"[:2000])
            raise
