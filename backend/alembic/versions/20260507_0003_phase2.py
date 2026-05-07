"""phase 2: outline_node_versions + style_profiles

Revision ID: 20260507_0003
Revises: 20260506_0002
Create Date: 2026-05-07

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260507_0003"
down_revision: Union[str, None] = "20260506_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "outline_node_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "outline_node_id",
            sa.Integer(),
            sa.ForeignKey("outline_nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("body_md", sa.Text(), nullable=True),
        sa.Column("label", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index(
        "ix_outline_node_versions_node",
        "outline_node_versions",
        ["outline_node_id"],
    )

    op.create_table(
        "style_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("name", sa.String(120), nullable=False, server_default="default"),
        sa.Column(
            "samples",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("profile_md", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_style_profiles_user", "style_profiles", ["user_id"])
    op.create_index("ix_style_profiles_project", "style_profiles", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_style_profiles_project", table_name="style_profiles")
    op.drop_index("ix_style_profiles_user", table_name="style_profiles")
    op.drop_table("style_profiles")
    op.drop_index("ix_outline_node_versions_node", table_name="outline_node_versions")
    op.drop_table("outline_node_versions")
