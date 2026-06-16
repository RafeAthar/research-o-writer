from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import require_auth
from app.services.scope import resolve_source_ids
from app.services.search import (
    RetrievedChunk,
    exact_phrase_search,
    hybrid_search,
    lexical_search,
    semantic_search,
)

router = APIRouter(prefix="/search", tags=["search"])


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    mode: str = Field(default="hybrid", pattern="^(hybrid|semantic|lexical|exact)$")
    source_ids: list[int] | None = None
    # When set, confine the search to this project's shelf (an empty shelf
    # returns no hits). Takes precedence over source_ids.
    project_id: int | None = None
    k: int = Field(default=10, ge=1, le=100)
    rerank: bool = True


class SearchHit(BaseModel):
    chunk_id: int
    source_id: int
    source_title: str
    chapter_path: list[str]
    page_start: int | None = None
    page_end: int | None = None
    paragraph_index: int | None = None
    char_start: int | None = None
    char_end: int | None = None
    text: str
    score: float


class SearchResponse(BaseModel):
    hits: list[SearchHit]


def _to_hit(rc: RetrievedChunk) -> SearchHit:
    return SearchHit(
        chunk_id=rc.chunk_id,
        source_id=rc.source_id,
        source_title=rc.source_title,
        chapter_path=rc.chapter_path,
        page_start=rc.page_start,
        page_end=rc.page_end,
        paragraph_index=rc.paragraph_index,
        char_start=rc.char_start,
        char_end=rc.char_end,
        text=rc.text,
        score=rc.score,
    )


@router.post("", response_model=SearchResponse)
async def search(
    req: SearchRequest,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    scope = "project" if req.project_id is not None else "sources"
    source_ids = await resolve_source_ids(
        db,
        user_id=user_id,
        scope=scope,
        source_ids=req.source_ids,
        project_id=req.project_id,
    )
    # Empty list == "search nothing" (e.g. an empty project shelf); short-circuit
    # since the search helpers treat a falsy source_ids as "no filter".
    if source_ids == []:
        return SearchResponse(hits=[])

    if req.mode == "hybrid":
        hits = await hybrid_search(
            db,
            user_id=user_id,
            query=req.query,
            k_final=req.k,
            source_ids=source_ids,
            rerank=req.rerank,
        )
    else:
        if req.mode == "semantic":
            raw = await semantic_search(
                db, user_id=user_id, query=req.query, k=req.k, source_ids=source_ids
            )
        elif req.mode == "lexical":
            raw = await lexical_search(
                db, user_id=user_id, query=req.query, k=req.k, source_ids=source_ids
            )
        else:
            raw = await exact_phrase_search(
                db, user_id=user_id, phrase=req.query, k=req.k, source_ids=source_ids
            )
        hits = [
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
                score=float(s),
            )
            for c, s, title in raw
        ]
    return SearchResponse(hits=[_to_hit(h) for h in hits])
