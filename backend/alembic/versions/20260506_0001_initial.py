"""initial schema

Revision ID: 20260506_0001
Revises:
Create Date: 2026-05-06

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "20260506_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


EMBEDDING_DIM = 1024


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=True, unique=True),
        sa.Column("display_name", sa.String(120), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # Seed the single Phase-1 user with id=1 to match APP_DEFAULT_USER_ID.
    op.execute(
        "INSERT INTO users (id, email, display_name) "
        "VALUES (1, NULL, 'default') ON CONFLICT DO NOTHING"
    )
    op.execute("SELECT setval(pg_get_serial_sequence('users', 'id'), GREATEST((SELECT max(id) FROM users), 1))")

    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("authors", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("publisher", sa.String(256), nullable=True),
        sa.Column("isbn", sa.String(32), nullable=True),
        sa.Column("doi", sa.String(128), nullable=True),
        sa.Column("language", sa.String(16), nullable=True),
        sa.Column("source_format", sa.String(16), nullable=False),
        sa.Column("original_object_key", sa.String(512), nullable=False),
        sa.Column("original_filename", sa.String(512), nullable=True),
        sa.Column("original_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("original_sha256", sa.String(64), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=True),
        sa.Column("abstract", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="uploaded"),
        sa.Column("ingestion_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_sources_user_id", "sources", ["user_id"])
    op.create_index("ix_sources_isbn", "sources", ["isbn"])
    op.create_index("ix_sources_doi", "sources", ["doi"])
    op.create_index("ix_sources_sha256", "sources", ["original_sha256"])

    op.create_table(
        "source_structure",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("source_structure.id", ondelete="CASCADE"), nullable=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("chapter_path", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("depth", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("order_in_parent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
    )
    op.create_index("ix_source_structure_source", "source_structure", ["source_id"])
    op.create_index("ix_source_structure_parent", "source_structure", ["parent_id"])

    op.create_table(
        "chunks",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chapter_path", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("paragraph_index", sa.Integer(), nullable=True),
        sa.Column("char_start", sa.Integer(), nullable=True),
        sa.Column("char_end", sa.Integer(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("embedding_model_version", sa.String(128), nullable=True),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column("fts", postgresql.TSVECTOR(), nullable=True),
    )
    op.create_index("ix_chunks_source", "chunks", ["source_id"])
    op.create_index("ix_chunks_user", "chunks", ["user_id"])

    # FTS auto-update trigger: keep the tsvector in sync with text.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION chunks_fts_trigger() RETURNS trigger AS $$
        BEGIN
          NEW.fts := to_tsvector('english', coalesce(NEW.text, ''));
          RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER chunks_fts_update
        BEFORE INSERT OR UPDATE OF text ON chunks
        FOR EACH ROW EXECUTE FUNCTION chunks_fts_trigger();
        """
    )

    op.execute(
        "CREATE INDEX ix_chunks_fts ON chunks USING gin (fts)"
    )
    op.execute(
        "CREATE INDEX ix_chunks_embedding_hnsw ON chunks "
        "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
    )

    op.create_table(
        "highlights",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_id", sa.BigInteger(), sa.ForeignKey("chunks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("char_start", sa.Integer(), nullable=True),
        sa.Column("char_end", sa.Integer(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("color", sa.String(16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_highlights_user", "highlights", ["user_id"])
    op.create_index("ix_highlights_source", "highlights", ["source_id"])
    op.create_index("ix_highlights_chunk", "highlights", ["chunk_id"])

    op.create_table(
        "quote_shelf",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_id", sa.BigInteger(), sa.ForeignKey("chunks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("citation", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_quote_shelf_user", "quote_shelf", ["user_id"])
    op.create_index("ix_quote_shelf_source", "quote_shelf", ["source_id"])
    op.create_index("ix_quote_shelf_chunk", "quote_shelf", ["chunk_id"])

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_projects_user", "projects", ["user_id"])

    op.create_table(
        "outline_nodes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("outline_nodes.id", ondelete="CASCADE"), nullable=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False, server_default="section"),
        sa.Column("order_in_parent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("body_md", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_outline_nodes_project", "outline_nodes", ["project_id"])
    op.create_index("ix_outline_nodes_parent", "outline_nodes", ["parent_id"])

    op.create_table(
        "evidence_cards",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "outline_node_id",
            sa.Integer(),
            sa.ForeignKey("outline_nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_id", sa.BigInteger(), sa.ForeignKey("chunks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("highlight_id", sa.BigInteger(), sa.ForeignKey("highlights.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "quote_shelf_id",
            sa.BigInteger(),
            sa.ForeignKey("quote_shelf.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("quote_text", sa.Text(), nullable=False),
        sa.Column("citation", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("order_in_node", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_evidence_node", "evidence_cards", ["outline_node_id"])
    op.create_index("ix_evidence_source", "evidence_cards", ["source_id"])
    op.create_index("ix_evidence_chunk", "evidence_cards", ["chunk_id"])


def downgrade() -> None:
    op.drop_table("evidence_cards")
    op.drop_table("outline_nodes")
    op.drop_table("projects")
    op.drop_table("quote_shelf")
    op.drop_table("highlights")
    op.execute("DROP TRIGGER IF EXISTS chunks_fts_update ON chunks")
    op.execute("DROP FUNCTION IF EXISTS chunks_fts_trigger()")
    op.drop_table("chunks")
    op.drop_table("source_structure")
    op.drop_table("sources")
    op.drop_table("users")
