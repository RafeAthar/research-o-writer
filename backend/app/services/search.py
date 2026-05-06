"""Hybrid retrieval over chunks: semantic (pgvector) + lexical (FTS) +
optional reranking via cross-encoder. Returns chunks with full citation
metadata for paragraph-level citations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import bindparam, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source import Chunk, Source
from app.services.embedder import embed_query
from app.services.reranker import rerank as cross_rerank

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    chunk_id: int
    source_id: int
    source_title: str
    chapter_path: list[str]
    page_start: int | None
    page_end: int | None
    paragraph_index: int | None
    char_start: int | None
    char_end: int | None
    text: str
    score: float

    def citation_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "source_id": self.source_id,
            "source_title": self.source_title,
            "chapter_path": self.chapter_path,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "paragraph_index": self.paragraph_index,
        }


async def semantic_search(
    db: AsyncSession,
    *,
    user_id: int,
    query: str,
    k: int = 50,
    source_ids: list[int] | None = None,
) -> list[tuple[Chunk, float, str]]:
    """Returns (chunk, similarity_score, source_title)."""
    qvec = embed_query(query)
    stmt = (
        select(
            Chunk,
            (1 - Chunk.embedding.cosine_distance(qvec)).label("similarity"),
            Source.title.label("source_title"),
        )
        .join(Source, Source.id == Chunk.source_id)
        .where(Chunk.user_id == user_id, Chunk.embedding.is_not(None))
    )
    if source_ids:
        stmt = stmt.where(Chunk.source_id.in_(source_ids))
    stmt = stmt.order_by(Chunk.embedding.cosine_distance(qvec)).limit(k)

    rows = (await db.execute(stmt)).all()
    return [(r[0], float(r[1]), r[2]) for r in rows]


async def lexical_search(
    db: AsyncSession,
    *,
    user_id: int,
    query: str,
    k: int = 50,
    source_ids: list[int] | None = None,
) -> list[tuple[Chunk, float, str]]:
    """FTS over chunks.fts using websearch_to_tsquery (forgiving syntax)."""
    tsq = func.websearch_to_tsquery("english", query)
    stmt = (
        select(
            Chunk,
            func.ts_rank_cd(Chunk.fts, tsq).label("rank"),
            Source.title.label("source_title"),
        )
        .join(Source, Source.id == Chunk.source_id)
        .where(Chunk.user_id == user_id, Chunk.fts.op("@@")(tsq))
    )
    if source_ids:
        stmt = stmt.where(Chunk.source_id.in_(source_ids))
    stmt = stmt.order_by(text("rank DESC")).limit(k)

    rows = (await db.execute(stmt)).all()
    return [(r[0], float(r[1]), r[2]) for r in rows]


async def exact_phrase_search(
    db: AsyncSession,
    *,
    user_id: int,
    phrase: str,
    k: int = 50,
    source_ids: list[int] | None = None,
) -> list[tuple[Chunk, float, str]]:
    """Strict substring match (case-insensitive). Useful for proper nouns
    and term-of-art lookups where FTS stemming breaks intent."""
    like = f"%{phrase}%"
    stmt = (
        select(Chunk, Source.title.label("source_title"))
        .join(Source, Source.id == Chunk.source_id)
        .where(Chunk.user_id == user_id, Chunk.text.ilike(bindparam("p")))
        .params(p=like)
    )
    if source_ids:
        stmt = stmt.where(Chunk.source_id.in_(source_ids))
    stmt = stmt.limit(k)
    rows = (await db.execute(stmt)).all()
    # Score is just 1.0; ranking is by insertion order (no notion of relevance here).
    return [(r[0], 1.0, r[1]) for r in rows]


async def hybrid_search(
    db: AsyncSession,
    *,
    user_id: int,
    query: str,
    k_semantic: int = 50,
    k_lexical: int = 50,
    rerank_top: int = 30,
    k_final: int = 10,
    source_ids: list[int] | None = None,
    rerank: bool = True,
) -> list[RetrievedChunk]:
    """Reciprocal Rank Fusion of semantic + lexical, then cross-encoder rerank."""
    sem = await semantic_search(
        db, user_id=user_id, query=query, k=k_semantic, source_ids=source_ids
    )
    lex = await lexical_search(
        db, user_id=user_id, query=query, k=k_lexical, source_ids=source_ids
    )

    rrf_k = 60
    rrf: dict[int, float] = {}
    chunk_map: dict[int, tuple[Chunk, str]] = {}

    for rank, (c, _s, title) in enumerate(sem):
        rrf[c.id] = rrf.get(c.id, 0.0) + 1.0 / (rrf_k + rank + 1)
        chunk_map[c.id] = (c, title)
    for rank, (c, _s, title) in enumerate(lex):
        rrf[c.id] = rrf.get(c.id, 0.0) + 1.0 / (rrf_k + rank + 1)
        chunk_map[c.id] = (c, title)

    merged = sorted(rrf.items(), key=lambda x: x[1], reverse=True)[:rerank_top]
    if not merged:
        return []

    if rerank:
        try:
            pairs = [(cid, chunk_map[cid][0].text) for cid, _ in merged]
            scored = cross_rerank(query, pairs)[:k_final]
        except Exception as e:
            logger.warning("rerank failed, falling back to RRF order: %s", e)
            scored = [(cid, score) for cid, score in merged[:k_final]]
    else:
        scored = [(cid, score) for cid, score in merged[:k_final]]

    out: list[RetrievedChunk] = []
    for cid, score in scored:
        c, title = chunk_map[cid]
        out.append(
            RetrievedChunk(
                chunk_id=c.id,
                source_id=c.source_id,
                source_title=title,
                chapter_path=list(c.chapter_path or []),
                page_start=c.page_start,
                page_end=c.page_end,
                paragraph_index=c.paragraph_index,
                char_start=c.char_start,
                char_end=c.char_end,
                text=c.text,
                score=float(score),
            )
        )
    return out
