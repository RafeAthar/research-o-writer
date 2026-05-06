from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import require_auth
from app.models.source import Source, SourceStatus
from app.services.parsers.dispatch import UnsupportedFormatError, detect_format
from app.services.storage import Storage, content_addressed_key, sha256_hex
from app.workers.ingest import ingest_source
from app.workers.queue import get_queue

router = APIRouter(prefix="/sources", tags=["sources"])


class SourceOut(BaseModel):
    id: int
    title: str
    authors: list[str]
    year: int | None
    publisher: str | None
    isbn: str | None
    doi: str | None
    language: str | None
    source_format: str
    page_count: int | None
    word_count: int | None
    status: str
    ingestion_error: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


@router.post("", response_model=SourceOut, status_code=status.HTTP_201_CREATED)
async def upload_source(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> SourceOut:
    try:
        fmt = detect_format(file.filename, file.content_type)
    except UnsupportedFormatError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    digest = sha256_hex(data)

    # De-dup by sha256 within the user's library.
    existing = (
        await db.execute(
            select(Source).where(Source.user_id == user_id, Source.original_sha256 == digest)
        )
    ).scalar_one_or_none()
    if existing:
        return SourceOut.model_validate(existing)

    storage = Storage()
    key = content_addressed_key("sources", data, suffix=fmt.value)
    storage.put_bytes(key, data, content_type=file.content_type)

    src = Source(
        user_id=user_id,
        title=title or (file.filename or "Untitled"),
        authors=[],
        source_format=fmt.value,
        original_object_key=key,
        original_filename=file.filename,
        original_size_bytes=len(data),
        original_sha256=digest,
        status=SourceStatus.UPLOADED.value,
    )
    db.add(src)
    await db.commit()
    await db.refresh(src)

    get_queue("ingest").enqueue(ingest_source, src.id, job_timeout=3600)
    return SourceOut.model_validate(src)


@router.get("", response_model=list[SourceOut])
async def list_sources(
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> list[SourceOut]:
    rows = (
        await db.execute(
            select(Source).where(Source.user_id == user_id).order_by(Source.created_at.desc())
        )
    ).scalars().all()
    return [SourceOut.model_validate(r) for r in rows]


@router.get("/{source_id}", response_model=SourceOut)
async def get_source(
    source_id: int,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> SourceOut:
    row = (
        await db.execute(
            select(Source).where(Source.id == source_id, Source.user_id == user_id)
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="source not found")
    return SourceOut.model_validate(row)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: int,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> None:
    row = (
        await db.execute(
            select(Source).where(Source.id == source_id, Source.user_id == user_id)
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="source not found")
    Storage().delete(row.original_object_key)
    await db.delete(row)
    await db.commit()
