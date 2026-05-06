"""Ingestion pipeline (synchronous; runs inside an RQ worker).

Steps:
  1. Load original bytes from object storage.
  2. Parse to a structural tree.
  3. Persist source_structure rows.
  4. Chunk paragraphs.
  5. Insert chunks (FTS auto-populates via DB trigger).
  6. Enrich metadata via ISBN/DOI when present.

Embedding (1.4) is queued separately at the end.
"""

from __future__ import annotations

import logging
import re

from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models.source import Chunk, Source, SourceStatus, SourceStructure
from app.services.chunker import chunk_paragraphs
from app.services.metadata_enrichment import enrich_by_doi, enrich_by_isbn
from app.services.parsers import parse
from app.services.parsers.types import StructureNode
from app.services.storage import Storage

logger = logging.getLogger(__name__)

ISBN_RE = re.compile(r"\b97[89][\d\-]{10,17}\b|\b\d{9}[\dXx]\b")
DOI_RE = re.compile(r"\b10\.\d{4,9}/[^\s\"<>]+", re.IGNORECASE)


def _sync_engine():
    s = get_settings()
    return create_engine(s.database_url_sync, pool_pre_ping=True, future=True)


def _set_status(
    db: Session, source_id: int, status: SourceStatus, error: str | None = None
) -> None:
    db.execute(
        update(Source)
        .where(Source.id == source_id)
        .values(status=status.value, ingestion_error=error)
    )
    db.commit()


def _persist_structure(db: Session, source_id: int, roots: list[StructureNode]) -> None:
    def insert(nodes: list[StructureNode], parent_id: int | None) -> None:
        for n in nodes:
            row = SourceStructure(
                source_id=source_id,
                parent_id=parent_id,
                title=n.title,
                chapter_path=n.chapter_path,
                depth=n.depth,
                order_in_parent=n.order_in_parent,
                page_start=n.page_start,
                page_end=n.page_end,
            )
            db.add(row)
            db.flush()
            insert(n.children, row.id)

    insert(roots, None)
    db.commit()


def _maybe_enrich(db: Session, source_id: int, full_text_head: str) -> None:
    """Try to find an ISBN/DOI in the first ~10 KB of text, then enrich."""
    src = db.execute(select(Source).where(Source.id == source_id)).scalar_one()
    head = full_text_head[:10000]

    isbn_match = src.isbn or (m.group(0) if (m := ISBN_RE.search(head)) else None)
    doi_match = src.doi or (m.group(0) if (m := DOI_RE.search(head)) else None)

    enriched = None
    if isbn_match:
        enriched = enrich_by_isbn(isbn_match.replace("-", ""))
    elif doi_match:
        enriched = enrich_by_doi(doi_match)

    if not enriched:
        return

    updates: dict = {}
    if enriched.title and not src.title:
        updates["title"] = enriched.title
    if enriched.authors and not src.authors:
        updates["authors"] = enriched.authors
    if enriched.year and not src.year:
        updates["year"] = enriched.year
    if enriched.publisher and not src.publisher:
        updates["publisher"] = enriched.publisher
    if enriched.language and not src.language:
        updates["language"] = enriched.language
    if enriched.isbn and not src.isbn:
        updates["isbn"] = enriched.isbn
    if enriched.doi and not src.doi:
        updates["doi"] = enriched.doi

    if updates:
        db.execute(update(Source).where(Source.id == source_id).values(**updates))
        db.commit()


def ingest_source(source_id: int) -> None:
    """RQ entrypoint. Runs the full ingestion pipeline for one source."""
    Engine = _sync_engine()
    SessionFactory = sessionmaker(bind=Engine, expire_on_commit=False)
    storage = Storage()

    with SessionFactory() as db:
        try:
            src = db.execute(select(Source).where(Source.id == source_id)).scalar_one()

            _set_status(db, source_id, SourceStatus.EXTRACTING)
            data = storage.get_bytes(src.original_object_key)
            from app.models.source import SourceFormat

            fmt = SourceFormat(src.source_format)
            doc = parse(fmt, data, filename=src.original_filename)

            # Apply parsed-doc metadata to source where not already set.
            updates: dict = {
                "page_count": doc.page_count,
                "word_count": doc.word_count,
            }
            if not src.title and doc.title:
                updates["title"] = doc.title
            if not src.authors and doc.authors:
                updates["authors"] = doc.authors
            if not src.language and doc.language:
                updates["language"] = doc.language
            db.execute(update(Source).where(Source.id == source_id).values(**updates))
            db.commit()

            _persist_structure(db, source_id, doc.structure)

            _set_status(db, source_id, SourceStatus.CHUNKING)
            chunks = chunk_paragraphs(doc.paragraphs)
            for ch in chunks:
                row = Chunk(
                    source_id=source_id,
                    user_id=src.user_id,
                    chapter_path=ch.chapter_path,
                    page_start=ch.page_start,
                    page_end=ch.page_end,
                    paragraph_index=ch.paragraph_index,
                    char_start=ch.char_start,
                    char_end=ch.char_end,
                    text=ch.text,
                    token_count=ch.token_count,
                )
                db.add(row)
            db.commit()

            _maybe_enrich(db, source_id, doc.full_text)

            # Embedding queued separately (Phase 1.4).
            try:
                from app.workers.embed import embed_source  # noqa: WPS433
                from app.workers.queue import get_queue

                _set_status(db, source_id, SourceStatus.EMBEDDING)
                get_queue("embed").enqueue(embed_source, source_id, job_timeout=3600)
            except Exception as e:
                logger.warning("embed enqueue failed (will mark ready without vectors): %s", e)
                _set_status(db, source_id, SourceStatus.READY)

        except Exception as e:
            logger.exception("ingestion failed for source %s", source_id)
            _set_status(db, source_id, SourceStatus.FAILED, error=str(e)[:2000])
            raise
