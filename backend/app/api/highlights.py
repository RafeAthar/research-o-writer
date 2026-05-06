"""Highlights API: user-saved spans on a source."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import require_auth
from app.models.library import Highlight
from app.models.source import Source

router = APIRouter(prefix="/highlights", tags=["highlights"])


class HighlightCreate(BaseModel):
    source_id: int
    chunk_id: int | None = None
    page: int | None = None
    char_start: int | None = None
    char_end: int | None = None
    text: str = Field(..., min_length=1)
    note: str | None = None
    color: str | None = None


class HighlightUpdate(BaseModel):
    note: str | None = None
    color: str | None = None


class HighlightOut(BaseModel):
    id: int
    source_id: int
    chunk_id: int | None
    page: int | None
    char_start: int | None
    char_end: int | None
    text: str
    note: str | None
    color: str | None
    created_at: datetime

    class Config:
        from_attributes = True


async def _own_source(db: AsyncSession, user_id: int, source_id: int) -> Source:
    src = (
        await db.execute(
            select(Source).where(Source.id == source_id, Source.user_id == user_id)
        )
    ).scalar_one_or_none()
    if not src:
        raise HTTPException(404, "source not found")
    return src


@router.post("", response_model=HighlightOut, status_code=status.HTTP_201_CREATED)
async def create_highlight(
    body: HighlightCreate,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> HighlightOut:
    await _own_source(db, user_id, body.source_id)
    h = Highlight(
        user_id=user_id,
        source_id=body.source_id,
        chunk_id=body.chunk_id,
        page=body.page,
        char_start=body.char_start,
        char_end=body.char_end,
        text=body.text,
        note=body.note,
        color=body.color,
    )
    db.add(h)
    await db.commit()
    await db.refresh(h)
    return HighlightOut.model_validate(h)


@router.get("", response_model=list[HighlightOut])
async def list_highlights(
    source_id: int | None = Query(default=None),
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> list[HighlightOut]:
    stmt = select(Highlight).where(Highlight.user_id == user_id)
    if source_id is not None:
        stmt = stmt.where(Highlight.source_id == source_id)
    rows = (await db.execute(stmt.order_by(Highlight.id.desc()))).scalars().all()
    return [HighlightOut.model_validate(r) for r in rows]


@router.patch("/{highlight_id}", response_model=HighlightOut)
async def update_highlight(
    highlight_id: int,
    body: HighlightUpdate,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> HighlightOut:
    h = (
        await db.execute(
            select(Highlight).where(Highlight.id == highlight_id, Highlight.user_id == user_id)
        )
    ).scalar_one_or_none()
    if not h:
        raise HTTPException(404, "highlight not found")
    if body.note is not None:
        h.note = body.note
    if body.color is not None:
        h.color = body.color
    await db.commit()
    await db.refresh(h)
    return HighlightOut.model_validate(h)


@router.delete("/{highlight_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_highlight(
    highlight_id: int,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> None:
    h = (
        await db.execute(
            select(Highlight).where(Highlight.id == highlight_id, Highlight.user_id == user_id)
        )
    ).scalar_one_or_none()
    if not h:
        raise HTTPException(404, "highlight not found")
    await db.delete(h)
    await db.commit()
