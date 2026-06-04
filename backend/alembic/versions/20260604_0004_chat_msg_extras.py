"""chat_messages: suggestions + stop_reason

Revision ID: 20260604_0004
Revises: 20260507_0003
Create Date: 2026-06-04

Adds:
- chat_messages.suggestions JSONB nullable — follow-up question chips
- chat_messages.stop_reason VARCHAR(32) nullable — Anthropic stop_reason
  ("end_turn", "max_tokens", "stop_sequence", "tool_use", "client_abort", ...)
  Used to surface a "Continue" affordance when generation hits max_tokens.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260604_0004"
down_revision: Union[str, None] = "20260507_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chat_messages",
        sa.Column("suggestions", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "chat_messages",
        sa.Column("stop_reason", sa.String(32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chat_messages", "stop_reason")
    op.drop_column("chat_messages", "suggestions")
