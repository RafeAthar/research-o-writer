from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin


class Project(Base, TimestampMixin):
    """A book or article being written."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    nodes: Mapped[list[OutlineNode]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class OutlineNode(Base, TimestampMixin):
    """A node in a project's outline tree."""

    __tablename__ = "outline_nodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("outline_nodes.id", ondelete="CASCADE"), nullable=True, index=True
    )

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), default="section", nullable=False)
    order_in_parent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    body_md: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped[Project] = relationship(back_populates="nodes")
    evidence: Mapped[list[EvidenceCard]] = relationship(
        back_populates="node", cascade="all, delete-orphan"
    )


class EvidenceCard(Base, TimestampMixin):
    """A pinned quote/passage attached to an outline node, with its citation."""

    __tablename__ = "evidence_cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    outline_node_id: Mapped[int] = mapped_column(
        ForeignKey("outline_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_id: Mapped[int | None] = mapped_column(
        ForeignKey("chunks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    highlight_id: Mapped[int | None] = mapped_column(
        ForeignKey("highlights.id", ondelete="SET NULL"), nullable=True, index=True
    )
    quote_shelf_id: Mapped[int | None] = mapped_column(
        ForeignKey("quote_shelf.id", ondelete="SET NULL"), nullable=True, index=True
    )

    quote_text: Mapped[str] = mapped_column(Text, nullable=False)
    citation: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_in_node: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    node: Mapped[OutlineNode] = relationship(back_populates="evidence")


class OutlineNodeVersion(Base, TimestampMixin):
    """A snapshot of an outline node's title + body, for history & diff view."""

    __tablename__ = "outline_node_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    outline_node_id: Mapped[int] = mapped_column(
        ForeignKey("outline_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    body_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)


class StyleProfile(Base, TimestampMixin):
    """A per-user (optionally per-project) style profile distilled from past writing.

    `samples` holds the raw text excerpts used to build the profile;
    `profile_md` is the generated style description injected into chat /
    draft prompts when the project has a profile.
    """

    __tablename__ = "style_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False, default="default")
    samples: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    profile_md: Mapped[str | None] = mapped_column(Text, nullable=True)
