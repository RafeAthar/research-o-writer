from __future__ import annotations

from enum import StrEnum

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import get_settings
from app.db import Base
from app.models.base import TimestampMixin

_EMB_DIM = get_settings().embedding_dim


class SourceFormat(StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    EPUB = "epub"
    HTML = "html"
    MARKDOWN = "markdown"
    TEXT = "text"


class SourceStatus(StrEnum):
    UPLOADED = "uploaded"
    EXTRACTING = "extracting"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    READY = "ready"
    FAILED = "failed"


class Source(Base, TimestampMixin):
    """A book/article/document the user has added to their library."""

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    authors: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(256), nullable=True)
    isbn: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    doi: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)

    source_format: Mapped[str] = mapped_column(String(16), nullable=False)

    original_object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    original_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    original_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        String(16), default=SourceStatus.UPLOADED.value, nullable=False
    )
    ingestion_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    structure: Mapped[list[SourceStructure]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )
    chunks: Mapped[list[Chunk]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class SourceStructure(Base):
    """Hierarchical TOC for a source: chapters/sections/subsections."""

    __tablename__ = "source_structure"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("source_structure.id", ondelete="CASCADE"), nullable=True, index=True
    )

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    chapter_path: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    order_in_parent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)

    source: Mapped[Source] = relationship(back_populates="structure")


class Chunk(Base):
    """A retrievable passage with full citation metadata + embedding + FTS."""

    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    chapter_path: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    paragraph_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_end: Mapped[int | None] = mapped_column(Integer, nullable=True)

    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    embedding_model_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(_EMB_DIM), nullable=True)

    fts: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)

    source: Mapped[Source] = relationship(back_populates="chunks")

    __table_args__ = (
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_chunks_fts", "fts", postgresql_using="gin"),
    )
