"""project_sources: per-project source shelf

Revision ID: 20260604_0005
Revises: 20260604_0004
Create Date: 2026-06-04

Adds the project_sources join table: an explicit many-to-many membership of
library sources on a project's shelf. Project-scoped chat/search retrieve only
from a project's attached sources. References, not copies — chunks/embeddings
stay on the source; detaching just removes the link.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260604_0005"
down_revision: Union[str, None] = "20260604_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "project_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "source_id", name="uq_project_sources_project_source"),
    )
    op.create_index("ix_project_sources_project_id", "project_sources", ["project_id"])
    op.create_index("ix_project_sources_source_id", "project_sources", ["source_id"])
    op.create_index("ix_project_sources_user_id", "project_sources", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_project_sources_user_id", table_name="project_sources")
    op.drop_index("ix_project_sources_source_id", table_name="project_sources")
    op.drop_index("ix_project_sources_project_id", table_name="project_sources")
    op.drop_table("project_sources")
