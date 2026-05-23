from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db
from app.deps import require_auth
from app.models.source import Chunk, Source, SourceStatus, SourceStructure
from app.services.parsers.dispatch import UnsupportedFormatError, detect_format
from app.services.storage import Storage, content_addressed_key, sha256_hex
from app.workers.ingest import ingest_source
from app.workers.queue import get_queue

router = APIRouter(prefix="/sources", tags=["sources"])

_MIME_BY_FORMAT = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "epub": "application/epub+zip",
    "html": "text/html; charset=utf-8",
    "markdown": "text/markdown; charset=utf-8",
    "text": "text/plain; charset=utf-8",
}


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
    max_mb = get_settings().max_upload_mb
    if len(data) > max_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"file exceeds {max_mb} MB limit")
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


@router.get("/{source_id}/file")
async def get_source_file(
    source_id: int,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> Response:
    row = (
        await db.execute(
            select(Source).where(Source.id == source_id, Source.user_id == user_id)
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="source not found")
    data = Storage().get_bytes(row.original_object_key)
    media_type = _MIME_BY_FORMAT.get(row.source_format, "application/octet-stream")
    headers = {"Cache-Control": "private, max-age=3600"}
    return Response(content=data, media_type=media_type, headers=headers)


class StructureNodeOut(BaseModel):
    id: int
    parent_id: int | None
    title: str
    chapter_path: list[str]
    depth: int
    order_in_parent: int
    page_start: int | None
    page_end: int | None

    class Config:
        from_attributes = True


@router.get("/{source_id}/structure", response_model=list[StructureNodeOut])
async def get_source_structure(
    source_id: int,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> list[StructureNodeOut]:
    src = (
        await db.execute(
            select(Source).where(Source.id == source_id, Source.user_id == user_id)
        )
    ).scalar_one_or_none()
    if not src:
        raise HTTPException(status_code=404, detail="source not found")
    rows = (
        await db.execute(
            select(SourceStructure)
            .where(SourceStructure.source_id == source_id)
            .order_by(SourceStructure.id)
        )
    ).scalars().all()
    return [StructureNodeOut.model_validate(r) for r in rows]


class ChunkOut(BaseModel):
    id: int
    source_id: int
    chapter_path: list[str]
    page_start: int | None
    page_end: int | None
    paragraph_index: int | None
    char_start: int | None
    char_end: int | None
    text: str

    class Config:
        from_attributes = True


@router.get("/{source_id}/chunks", response_model=list[ChunkOut])
async def list_source_chunks(
    source_id: int,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=1000),
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> list[ChunkOut]:
    src = (
        await db.execute(
            select(Source).where(Source.id == source_id, Source.user_id == user_id)
        )
    ).scalar_one_or_none()
    if not src:
        raise HTTPException(status_code=404, detail="source not found")
    rows = (
        await db.execute(
            select(Chunk)
            .where(Chunk.source_id == source_id)
            .order_by(Chunk.id)
            .offset(offset)
            .limit(limit)
        )
    ).scalars().all()
    return [ChunkOut.model_validate(r) for r in rows]
