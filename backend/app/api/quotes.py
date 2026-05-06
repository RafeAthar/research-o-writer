"""Quote shelf API: reusable saved quotes with full citation metadata.

Highlights are positional spans on a source. Quote-shelf items are *cross-project*
saved citations: the user's library of "things worth pulling into a piece of
writing". Distinct surface, distinct table.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import require_auth
from app.models.library import QuoteShelfItem
from app.models.source import Source

router = APIRouter(prefix="/quotes", tags=["quotes"])


class QuoteCreate(BaseModel):
    source_id: int
    chunk_id: int | None = None
    text: str = Field(..., min_length=1)
    citation: dict = Field(default_factory=dict)
    note: str | None = None


class QuoteUpdate(BaseModel):
    note: str | None = None


class QuoteOut(BaseModel):
    id: int
    source_id: int
    chunk_id: int | None
    text: str
    citation: dict
    note: str | None
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


@router.post("", response_model=QuoteOut, status_code=status.HTTP_201_CREATED)
async def create_quote(
    body: QuoteCreate,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> QuoteOut:
    await _own_source(db, user_id, body.source_id)
    q = QuoteShelfItem(
        user_id=user_id,
        source_id=body.source_id,
        chunk_id=body.chunk_id,
        text=body.text,
        citation=body.citation,
        note=body.note,
    )
    db.add(q)
    await db.commit()
    await db.refresh(q)
    return QuoteOut.model_validate(q)


@router.get("", response_model=list[QuoteOut])
async def list_quotes(
    source_id: int | None = Query(default=None),
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> list[QuoteOut]:
    stmt = select(QuoteShelfItem).where(QuoteShelfItem.user_id == user_id)
    if source_id is not None:
        stmt = stmt.where(QuoteShelfItem.source_id == source_id)
    rows = (await db.execute(stmt.order_by(QuoteShelfItem.id.desc()))).scalars().all()
    return [QuoteOut.model_validate(r) for r in rows]


@router.patch("/{quote_id}", response_model=QuoteOut)
async def update_quote(
    quote_id: int,
    body: QuoteUpdate,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> QuoteOut:
    q = (
        await db.execute(
            select(QuoteShelfItem).where(
                QuoteShelfItem.id == quote_id, QuoteShelfItem.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if not q:
        raise HTTPException(404, "quote not found")
    if body.note is not None:
        q.note = body.note
    await db.commit()
    await db.refresh(q)
    return QuoteOut.model_validate(q)


@router.delete("/{quote_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quote(
    quote_id: int,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> None:
    q = (
        await db.execute(
            select(QuoteShelfItem).where(
                QuoteShelfItem.id == quote_id, QuoteShelfItem.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if not q:
        raise HTTPException(404, "quote not found")
    await db.delete(q)
    await db.commit()
