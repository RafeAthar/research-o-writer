"""Projects API: outline trees + evidence cards.

A project is a piece of writing-in-progress. It has a tree of OutlineNodes
(parent_id, order_in_parent), each with a title and an optional markdown body.
Each node may have EvidenceCards: pinned quotes from sources with citation metadata.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import require_auth
from app.models.project import EvidenceCard, OutlineNode, Project
from app.models.source import Source
from app.services.export import render_project_markdown

router = APIRouter(prefix="/projects", tags=["projects"])


# ---------- Project ----------


class ProjectCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=512)
    description: str | None = None


class ProjectUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=512)
    description: str | None = None


class ProjectOut(BaseModel):
    id: int
    title: str
    description: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> ProjectOut:
    p = Project(user_id=user_id, title=body.title, description=body.description)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return ProjectOut.model_validate(p)


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> list[ProjectOut]:
    rows = (
        await db.execute(
            select(Project).where(Project.user_id == user_id).order_by(Project.updated_at.desc())
        )
    ).scalars().all()
    return [ProjectOut.model_validate(r) for r in rows]


async def _own_project(db: AsyncSession, user_id: int, project_id: int) -> Project:
    p = (
        await db.execute(
            select(Project).where(Project.id == project_id, Project.user_id == user_id)
        )
    ).scalar_one_or_none()
    if not p:
        raise HTTPException(404, "project not found")
    return p


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: int,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> ProjectOut:
    p = await _own_project(db, user_id, project_id)
    return ProjectOut.model_validate(p)


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: int,
    body: ProjectUpdate,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> ProjectOut:
    p = await _own_project(db, user_id, project_id)
    if body.title is not None:
        p.title = body.title
    if body.description is not None:
        p.description = body.description
    await db.commit()
    await db.refresh(p)
    return ProjectOut.model_validate(p)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> None:
    p = await _own_project(db, user_id, project_id)
    await db.delete(p)
    await db.commit()


# ---------- Outline nodes ----------


class OutlineNodeCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=512)
    parent_id: int | None = None
    kind: str = "section"
    order_in_parent: int = 0
    body_md: str | None = None


class OutlineNodeUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=512)
    parent_id: int | None = None
    kind: str | None = None
    order_in_parent: int | None = None
    body_md: str | None = None


class OutlineNodeOut(BaseModel):
    id: int
    project_id: int
    parent_id: int | None
    title: str
    kind: str
    order_in_parent: int
    body_md: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


async def _own_node(db: AsyncSession, user_id: int, project_id: int, node_id: int) -> OutlineNode:
    await _own_project(db, user_id, project_id)
    n = (
        await db.execute(
            select(OutlineNode).where(
                OutlineNode.id == node_id, OutlineNode.project_id == project_id
            )
        )
    ).scalar_one_or_none()
    if not n:
        raise HTTPException(404, "node not found")
    return n


@router.get("/{project_id}/nodes", response_model=list[OutlineNodeOut])
async def list_nodes(
    project_id: int,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> list[OutlineNodeOut]:
    await _own_project(db, user_id, project_id)
    rows = (
        await db.execute(
            select(OutlineNode)
            .where(OutlineNode.project_id == project_id)
            .order_by(OutlineNode.parent_id.nullsfirst(), OutlineNode.order_in_parent, OutlineNode.id)
        )
    ).scalars().all()
    return [OutlineNodeOut.model_validate(r) for r in rows]


@router.post("/{project_id}/nodes", response_model=OutlineNodeOut, status_code=201)
async def create_node(
    project_id: int,
    body: OutlineNodeCreate,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> OutlineNodeOut:
    await _own_project(db, user_id, project_id)
    if body.parent_id is not None:
        parent = (
            await db.execute(
                select(OutlineNode).where(
                    OutlineNode.id == body.parent_id, OutlineNode.project_id == project_id
                )
            )
        ).scalar_one_or_none()
        if not parent:
            raise HTTPException(400, "parent_id not in this project")
    n = OutlineNode(
        project_id=project_id,
        parent_id=body.parent_id,
        title=body.title,
        kind=body.kind,
        order_in_parent=body.order_in_parent,
        body_md=body.body_md,
    )
    db.add(n)
    await db.commit()
    await db.refresh(n)
    return OutlineNodeOut.model_validate(n)


@router.patch("/{project_id}/nodes/{node_id}", response_model=OutlineNodeOut)
async def update_node(
    project_id: int,
    node_id: int,
    body: OutlineNodeUpdate,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> OutlineNodeOut:
    n = await _own_node(db, user_id, project_id, node_id)
    if body.title is not None:
        n.title = body.title
    if body.kind is not None:
        n.kind = body.kind
    if body.order_in_parent is not None:
        n.order_in_parent = body.order_in_parent
    if body.body_md is not None:
        n.body_md = body.body_md
    if body.parent_id is not None or body.parent_id is None and "parent_id" in body.model_fields_set:
        n.parent_id = body.parent_id
    await db.commit()
    await db.refresh(n)
    return OutlineNodeOut.model_validate(n)


@router.delete("/{project_id}/nodes/{node_id}", status_code=204)
async def delete_node(
    project_id: int,
    node_id: int,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> None:
    n = await _own_node(db, user_id, project_id, node_id)
    await db.delete(n)
    await db.commit()


# ---------- Evidence cards ----------


class EvidenceCreate(BaseModel):
    outline_node_id: int
    source_id: int
    chunk_id: int | None = None
    quote_text: str = Field(..., min_length=1)
    citation: dict = Field(default_factory=dict)
    note: str | None = None
    order_in_node: int = 0


class EvidenceUpdate(BaseModel):
    quote_text: str | None = Field(default=None, min_length=1)
    note: str | None = None
    order_in_node: int | None = None
    outline_node_id: int | None = None


class EvidenceOut(BaseModel):
    id: int
    outline_node_id: int
    source_id: int
    chunk_id: int | None
    quote_text: str
    citation: dict
    note: str | None
    order_in_node: int
    created_at: datetime

    class Config:
        from_attributes = True


async def _own_evidence(db: AsyncSession, user_id: int, project_id: int, evidence_id: int) -> EvidenceCard:
    await _own_project(db, user_id, project_id)
    ec = (
        await db.execute(
            select(EvidenceCard)
            .join(OutlineNode, OutlineNode.id == EvidenceCard.outline_node_id)
            .where(EvidenceCard.id == evidence_id, OutlineNode.project_id == project_id)
        )
    ).scalar_one_or_none()
    if not ec:
        raise HTTPException(404, "evidence not found")
    return ec


@router.get("/{project_id}/evidence", response_model=list[EvidenceOut])
async def list_evidence(
    project_id: int,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> list[EvidenceOut]:
    await _own_project(db, user_id, project_id)
    rows = (
        await db.execute(
            select(EvidenceCard)
            .join(OutlineNode, OutlineNode.id == EvidenceCard.outline_node_id)
            .where(OutlineNode.project_id == project_id)
            .order_by(EvidenceCard.outline_node_id, EvidenceCard.order_in_node, EvidenceCard.id)
        )
    ).scalars().all()
    return [EvidenceOut.model_validate(r) for r in rows]


@router.post("/{project_id}/evidence", response_model=EvidenceOut, status_code=201)
async def create_evidence(
    project_id: int,
    body: EvidenceCreate,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> EvidenceOut:
    await _own_node(db, user_id, project_id, body.outline_node_id)
    ec = EvidenceCard(
        outline_node_id=body.outline_node_id,
        source_id=body.source_id,
        chunk_id=body.chunk_id,
        quote_text=body.quote_text,
        citation=body.citation,
        note=body.note,
        order_in_node=body.order_in_node,
    )
    db.add(ec)
    await db.commit()
    await db.refresh(ec)
    return EvidenceOut.model_validate(ec)


@router.patch("/{project_id}/evidence/{evidence_id}", response_model=EvidenceOut)
async def update_evidence(
    project_id: int,
    evidence_id: int,
    body: EvidenceUpdate,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> EvidenceOut:
    ec = await _own_evidence(db, user_id, project_id, evidence_id)
    if body.quote_text is not None:
        ec.quote_text = body.quote_text
    if body.note is not None:
        ec.note = body.note
    if body.order_in_node is not None:
        ec.order_in_node = body.order_in_node
    if body.outline_node_id is not None:
        await _own_node(db, user_id, project_id, body.outline_node_id)
        ec.outline_node_id = body.outline_node_id
    await db.commit()
    await db.refresh(ec)
    return EvidenceOut.model_validate(ec)


@router.delete("/{project_id}/evidence/{evidence_id}", status_code=204)
async def delete_evidence(
    project_id: int,
    evidence_id: int,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> None:
    ec = await _own_evidence(db, user_id, project_id, evidence_id)
    await db.delete(ec)
    await db.commit()


# ---------- Export ----------


@router.get("/{project_id}/export.md")
async def export_project_markdown(
    project_id: int,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> Response:
    project = await _own_project(db, user_id, project_id)
    nodes = (
        await db.execute(
            select(OutlineNode).where(OutlineNode.project_id == project_id)
        )
    ).scalars().all()
    evidence = (
        await db.execute(
            select(EvidenceCard)
            .join(OutlineNode, OutlineNode.id == EvidenceCard.outline_node_id)
            .where(OutlineNode.project_id == project_id)
        )
    ).scalars().all()

    cited_ids = {ec.source_id for ec in evidence}
    sources: list[Source] = []
    if cited_ids:
        sources = (
            await db.execute(
                select(Source).where(
                    Source.id.in_(cited_ids), Source.user_id == user_id
                )
            )
        ).scalars().all()
    sources_by_id = {s.id: s for s in sources}

    md = render_project_markdown(project, list(nodes), list(evidence), sources_by_id)
    safe = "".join(c if c.isalnum() else "-" for c in project.title.lower()).strip("-") or "project"
    return Response(
        content=md,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{safe}.md"',
        },
    )
