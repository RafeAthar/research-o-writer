"""Projects API: outline trees + evidence cards.

A project is a piece of writing-in-progress. It has a tree of OutlineNodes
(parent_id, order_in_parent), each with a title and an optional markdown body.
Each node may have EvidenceCards: pinned quotes from sources with citation metadata.
"""

from __future__ import annotations

import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.sources import SourceOut
from app.db import get_db
from app.deps import require_auth
from app.models.project import (
    EvidenceCard,
    OutlineNode,
    OutlineNodeVersion,
    Project,
    ProjectSource,
    StyleProfile,
)
from app.models.source import Source
from app.services.export import (
    CSL_STYLES,
    render_project_docx,
    render_project_markdown,
)
from app.services.writing_passes import (
    detect_contradictions,
    generate_style_profile,
    steel_man_section,
    whats_missing_section,
)

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


# ---------- Project source shelf ----------


class AttachSources(BaseModel):
    source_ids: list[int] = Field(..., min_length=1)


async def _attach_source(db: AsyncSession, user_id: int, project_id: int, source_id: int) -> None:
    """Idempotently link a source the user owns onto a project's shelf.

    Verifies ownership of the source; silently no-ops if already attached.
    Caller is responsible for committing.
    """
    src = (
        await db.execute(
            select(Source.id).where(Source.id == source_id, Source.user_id == user_id)
        )
    ).scalar_one_or_none()
    if src is None:
        raise HTTPException(404, f"source {source_id} not found")
    exists = (
        await db.execute(
            select(ProjectSource.id).where(
                ProjectSource.project_id == project_id,
                ProjectSource.source_id == source_id,
            )
        )
    ).scalar_one_or_none()
    if exists is None:
        db.add(ProjectSource(project_id=project_id, source_id=source_id, user_id=user_id))


@router.get("/{project_id}/sources", response_model=list[SourceOut])
async def list_project_sources(
    project_id: int,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> list[SourceOut]:
    await _own_project(db, user_id, project_id)
    rows = (
        await db.execute(
            select(Source)
            .join(ProjectSource, ProjectSource.source_id == Source.id)
            .where(ProjectSource.project_id == project_id)
            .order_by(Source.title)
        )
    ).scalars().all()
    return [SourceOut.model_validate(r) for r in rows]


@router.post("/{project_id}/sources", response_model=list[SourceOut], status_code=201)
async def attach_project_sources(
    project_id: int,
    body: AttachSources,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> list[SourceOut]:
    await _own_project(db, user_id, project_id)
    for source_id in dict.fromkeys(body.source_ids):
        await _attach_source(db, user_id, project_id, source_id)
    await db.commit()
    return await list_project_sources(project_id, user_id=user_id, db=db)


@router.delete("/{project_id}/sources/{source_id}", status_code=204)
async def detach_project_source(
    project_id: int,
    source_id: int,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> None:
    await _own_project(db, user_id, project_id)
    link = (
        await db.execute(
            select(ProjectSource).where(
                ProjectSource.project_id == project_id,
                ProjectSource.source_id == source_id,
            )
        )
    ).scalar_one_or_none()
    if link is None:
        raise HTTPException(404, "source not on this project's shelf")
    await db.delete(link)
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
    if "parent_id" in body.model_fields_set:
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
    # Pinning evidence from a source auto-attaches it to the project's shelf so
    # the shelf and the project's cited sources stay consistent.
    await _attach_source(db, user_id, project_id, body.source_id)
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


async def _load_export_bundle(
    db: AsyncSession, user_id: int, project_id: int
) -> tuple[Project, list[OutlineNode], list[EvidenceCard], dict[int, Source]]:
    project = await _own_project(db, user_id, project_id)
    nodes = (
        await db.execute(select(OutlineNode).where(OutlineNode.project_id == project_id))
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
                select(Source).where(Source.id.in_(cited_ids), Source.user_id == user_id)
            )
        ).scalars().all()
    return project, list(nodes), list(evidence), {s.id: s for s in sources}


def _safe_filename(title: str) -> str:
    safe = "".join(c if c.isalnum() else "-" for c in title.lower()).strip("-")
    return safe or "project"


@router.get("/{project_id}/export.md")
async def export_project_markdown(
    project_id: int,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> Response:
    project, nodes, evidence, sources_by_id = await _load_export_bundle(
        db, user_id, project_id
    )
    md = render_project_markdown(project, nodes, evidence, sources_by_id)
    safe = _safe_filename(project.title)
    return Response(
        content=md,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{safe}.md"'},
    )


@router.get("/{project_id}/export.docx")
async def export_project_docx(
    project_id: int,
    csl: str = "chicago",
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> Response:
    if csl not in CSL_STYLES:
        raise HTTPException(400, f"unknown csl style; choices: {sorted(CSL_STYLES)}")
    project, nodes, evidence, sources_by_id = await _load_export_bundle(
        db, user_id, project_id
    )
    try:
        blob = render_project_docx(
            project, nodes, evidence, sources_by_id, csl_style=csl
        )
    except RuntimeError as e:
        raise HTTPException(503, str(e)) from e
    safe = _safe_filename(project.title)
    return Response(
        content=blob,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{safe}.docx"'},
    )


# ---------- Versioned drafts ----------


class VersionCreate(BaseModel):
    label: str | None = Field(default=None, max_length=120)


class VersionOut(BaseModel):
    id: int
    outline_node_id: int
    title: str
    body_md: str | None
    label: str | None
    created_at: datetime

    class Config:
        from_attributes = True


@router.post(
    "/{project_id}/nodes/{node_id}/versions",
    response_model=VersionOut,
    status_code=201,
)
async def snapshot_node(
    project_id: int,
    node_id: int,
    body: VersionCreate,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> VersionOut:
    n = await _own_node(db, user_id, project_id, node_id)
    v = OutlineNodeVersion(
        outline_node_id=n.id,
        title=n.title,
        body_md=n.body_md,
        label=body.label,
    )
    db.add(v)
    await db.commit()
    await db.refresh(v)
    return VersionOut.model_validate(v)


@router.get(
    "/{project_id}/nodes/{node_id}/versions",
    response_model=list[VersionOut],
)
async def list_versions(
    project_id: int,
    node_id: int,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> list[VersionOut]:
    await _own_node(db, user_id, project_id, node_id)
    rows = (
        await db.execute(
            select(OutlineNodeVersion)
            .where(OutlineNodeVersion.outline_node_id == node_id)
            .order_by(OutlineNodeVersion.created_at.desc(), OutlineNodeVersion.id.desc())
        )
    ).scalars().all()
    return [VersionOut.model_validate(r) for r in rows]


async def _own_version(
    db: AsyncSession, user_id: int, project_id: int, node_id: int, version_id: int
) -> OutlineNodeVersion:
    await _own_node(db, user_id, project_id, node_id)
    v = (
        await db.execute(
            select(OutlineNodeVersion).where(
                OutlineNodeVersion.id == version_id,
                OutlineNodeVersion.outline_node_id == node_id,
            )
        )
    ).scalar_one_or_none()
    if not v:
        raise HTTPException(404, "version not found")
    return v


@router.get(
    "/{project_id}/nodes/{node_id}/versions/{version_id}",
    response_model=VersionOut,
)
async def get_version(
    project_id: int,
    node_id: int,
    version_id: int,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> VersionOut:
    v = await _own_version(db, user_id, project_id, node_id, version_id)
    return VersionOut.model_validate(v)


class VersionRestoreOut(BaseModel):
    restored_from: int
    node: OutlineNodeOut


@router.post(
    "/{project_id}/nodes/{node_id}/versions/{version_id}/restore",
    response_model=VersionRestoreOut,
)
async def restore_version(
    project_id: int,
    node_id: int,
    version_id: int,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> VersionRestoreOut:
    n = await _own_node(db, user_id, project_id, node_id)
    v = await _own_version(db, user_id, project_id, node_id, version_id)
    pre = OutlineNodeVersion(
        outline_node_id=n.id,
        title=n.title,
        body_md=n.body_md,
        label=f"auto-snapshot before restore of v{version_id}",
    )
    db.add(pre)
    n.title = v.title
    n.body_md = v.body_md
    await db.commit()
    await db.refresh(n)
    return VersionRestoreOut(
        restored_from=version_id, node=OutlineNodeOut.model_validate(n)
    )


# ---------- Coverage map ----------


class CoverageNode(BaseModel):
    node_id: int
    title: str
    parent_id: int | None
    depth: int
    evidence_count: int
    source_ids: list[int]


class CoverageSource(BaseModel):
    source_id: int
    title: str
    evidence_count: int


class CoverageOut(BaseModel):
    nodes: list[CoverageNode]
    sources: list[CoverageSource]
    matrix: list[list[int]]  # rows = nodes order, cols = sources order


@router.get("/{project_id}/coverage", response_model=CoverageOut)
async def coverage_map(
    project_id: int,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> CoverageOut:
    await _own_project(db, user_id, project_id)
    nodes = (
        await db.execute(
            select(OutlineNode)
            .where(OutlineNode.project_id == project_id)
            .order_by(
                OutlineNode.parent_id.nullsfirst(),
                OutlineNode.order_in_parent,
                OutlineNode.id,
            )
        )
    ).scalars().all()
    evidence = (
        await db.execute(
            select(EvidenceCard)
            .join(OutlineNode, OutlineNode.id == EvidenceCard.outline_node_id)
            .where(OutlineNode.project_id == project_id)
        )
    ).scalars().all()

    # Depth via parent traversal.
    by_id = {n.id: n for n in nodes}

    def _depth(n: OutlineNode) -> int:
        d = 0
        cur = n
        while cur.parent_id and cur.parent_id in by_id:
            cur = by_id[cur.parent_id]
            d += 1
            if d > 32:
                break
        return d

    src_ids = sorted({ec.source_id for ec in evidence})
    sources_rows: list[Source] = []
    if src_ids:
        sources_rows = (
            await db.execute(
                select(Source).where(
                    Source.id.in_(src_ids), Source.user_id == user_id
                )
            )
        ).scalars().all()
    src_title = {s.id: s.title for s in sources_rows}

    cov_nodes: list[CoverageNode] = []
    src_counts: dict[int, int] = {sid: 0 for sid in src_ids}
    matrix: list[list[int]] = []
    src_index = {sid: i for i, sid in enumerate(src_ids)}

    for n in nodes:
        ev_for = [ec for ec in evidence if ec.outline_node_id == n.id]
        sids = sorted({ec.source_id for ec in ev_for})
        cov_nodes.append(
            CoverageNode(
                node_id=n.id,
                title=n.title,
                parent_id=n.parent_id,
                depth=_depth(n),
                evidence_count=len(ev_for),
                source_ids=sids,
            )
        )
        row = [0] * len(src_ids)
        for ec in ev_for:
            i = src_index.get(ec.source_id)
            if i is not None:
                row[i] += 1
                src_counts[ec.source_id] = src_counts.get(ec.source_id, 0) + 1
        matrix.append(row)

    cov_sources = [
        CoverageSource(
            source_id=sid,
            title=src_title.get(sid, f"source {sid}"),
            evidence_count=src_counts.get(sid, 0),
        )
        for sid in src_ids
    ]
    return CoverageOut(nodes=cov_nodes, sources=cov_sources, matrix=matrix)


# ---------- Unsupported-sentence flagging ----------


class FlagSentencesIn(BaseModel):
    text: str = Field(..., min_length=1)


class FlaggedSentence(BaseModel):
    sentence: str
    char_start: int
    char_end: int
    supported: bool
    matched_evidence_ids: list[int]


class FlagSentencesOut(BaseModel):
    sentences: list[FlaggedSentence]


def _split_sentences(text: str) -> list[tuple[str, int, int]]:
    """Naive sentence splitter: ., !, ? terminators. Good enough for draft view."""
    out: list[tuple[str, int, int]] = []
    n = len(text)
    i = 0
    start = 0
    while i < n:
        c = text[i]
        if c in ".!?":
            j = i + 1
            while j < n and text[j] in ".!?\"'”’)":
                j += 1
            sent = text[start:j].strip()
            if sent:
                left = start + (len(text[start:j]) - len(text[start:j].lstrip()))
                out.append((sent, left, j))
            start = j
            i = j
            while start < n and text[start] in " \t\n\r":
                start += 1
            i = start
        else:
            i += 1
    if start < n:
        sent = text[start:].strip()
        if sent:
            left = start + (len(text[start:]) - len(text[start:].lstrip()))
            out.append((sent, left, n))
    return out


def _normalize(s: str) -> str:
    return " ".join(s.lower().split())


@router.post(
    "/{project_id}/nodes/{node_id}/flag-sentences",
    response_model=FlagSentencesOut,
)
async def flag_sentences(
    project_id: int,
    node_id: int,
    body: FlagSentencesIn,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> FlagSentencesOut:
    """Heuristic check: a sentence is 'supported' if it overlaps non-trivially
    with any pinned evidence quote on this node. Anti-hallucination guardrail
    for the draft view; LLM-grade verification can replace this later.
    """
    n = await _own_node(db, user_id, project_id, node_id)
    cards = (
        await db.execute(
            select(EvidenceCard).where(EvidenceCard.outline_node_id == n.id)
        )
    ).scalars().all()

    quotes = [(ec.id, _normalize(ec.quote_text)) for ec in cards]
    sents = _split_sentences(body.text)
    out: list[FlaggedSentence] = []
    for sent, cs, ce in sents:
        norm = _normalize(sent)
        if len(norm) < 12:
            out.append(
                FlaggedSentence(
                    sentence=sent,
                    char_start=cs,
                    char_end=ce,
                    supported=True,
                    matched_evidence_ids=[],
                )
            )
            continue
        toks = [t for t in norm.split() if len(t) > 3]
        matched: list[int] = []
        for ec_id, qnorm in quotes:
            if not qnorm:
                continue
            phrase_hit = any(
                " ".join(toks[i : i + 4]) and " ".join(toks[i : i + 4]) in qnorm
                for i in range(max(0, len(toks) - 3))
            )
            if phrase_hit:
                matched.append(ec_id)
                continue
            overlap = sum(1 for t in set(toks) if t in qnorm)
            if toks and overlap / max(1, len(set(toks))) >= 0.5:
                matched.append(ec_id)
        out.append(
            FlaggedSentence(
                sentence=sent,
                char_start=cs,
                char_end=ce,
                supported=bool(matched),
                matched_evidence_ids=matched,
            )
        )
    return FlagSentencesOut(sentences=out)


# ---------- Style profile (per-project) ----------


class StyleProfileOut(BaseModel):
    id: int
    user_id: int
    project_id: int | None
    name: str
    samples: list[str]
    profile_md: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StyleProfileWrite(BaseModel):
    name: str = "default"
    samples: list[str] = Field(default_factory=list)
    profile_md: str | None = None


async def _project_style(
    db: AsyncSession, user_id: int, project_id: int
) -> StyleProfile | None:
    return (
        await db.execute(
            select(StyleProfile).where(
                StyleProfile.user_id == user_id,
                StyleProfile.project_id == project_id,
            )
        )
    ).scalar_one_or_none()


@router.get("/{project_id}/style", response_model=StyleProfileOut | None)
async def get_style(
    project_id: int,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> StyleProfileOut | None:
    await _own_project(db, user_id, project_id)
    sp = await _project_style(db, user_id, project_id)
    return StyleProfileOut.model_validate(sp) if sp else None


@router.put("/{project_id}/style", response_model=StyleProfileOut)
async def upsert_style(
    project_id: int,
    body: StyleProfileWrite,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> StyleProfileOut:
    await _own_project(db, user_id, project_id)
    sp = await _project_style(db, user_id, project_id)
    if sp is None:
        sp = StyleProfile(
            user_id=user_id,
            project_id=project_id,
            name=body.name,
            samples=body.samples,
            profile_md=body.profile_md,
        )
        db.add(sp)
    else:
        sp.name = body.name
        sp.samples = body.samples
        if body.profile_md is not None:
            sp.profile_md = body.profile_md
    await db.commit()
    await db.refresh(sp)
    return StyleProfileOut.model_validate(sp)


@router.delete("/{project_id}/style", status_code=204)
async def delete_style(
    project_id: int,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> None:
    await _own_project(db, user_id, project_id)
    sp = await _project_style(db, user_id, project_id)
    if sp:
        await db.delete(sp)
        await db.commit()


@router.post("/{project_id}/style/generate", response_model=StyleProfileOut)
async def generate_style(
    project_id: int,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> StyleProfileOut:
    """Run the LLM style-distillation pass over the saved samples."""
    await _own_project(db, user_id, project_id)
    sp = await _project_style(db, user_id, project_id)
    if not sp or not sp.samples:
        raise HTTPException(400, "no samples saved; PUT /style with samples first")
    try:
        profile_md = await generate_style_profile(sp.samples)
    except Exception as e:  # surface upstream failure
        raise HTTPException(503, f"style generation failed: {e}") from e
    sp.profile_md = profile_md.strip()
    await db.commit()
    await db.refresh(sp)
    return StyleProfileOut.model_validate(sp)


# ---------- Contradiction detector ----------


class ContradictionIn(BaseModel):
    evidence_ids: list[int] = Field(default_factory=list)


class VerdictOut(BaseModel):
    pair: tuple[int, int]
    verdict: str
    rationale: str


class ContradictionOut(BaseModel):
    verdicts: list[VerdictOut]
    error: str | None = None


@router.post(
    "/{project_id}/nodes/{node_id}/contradictions",
    response_model=ContradictionOut,
)
async def contradictions(
    project_id: int,
    node_id: int,
    body: ContradictionIn,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> ContradictionOut:
    await _own_node(db, user_id, project_id, node_id)
    q = select(EvidenceCard).where(EvidenceCard.outline_node_id == node_id)
    if body.evidence_ids:
        q = q.where(EvidenceCard.id.in_(body.evidence_ids))
    cards = (await db.execute(q)).scalars().all()
    if len(cards) < 2:
        return ContradictionOut(verdicts=[])
    quotes = [
        (
            ec.id,
            (ec.citation or {}).get("source_title") or f"source {ec.source_id}",
            ec.quote_text,
        )
        for ec in cards
    ]
    try:
        results = await detect_contradictions(quotes)
    except Exception as e:
        return ContradictionOut(verdicts=[], error=str(e)[:300])
    return ContradictionOut(
        verdicts=[
            VerdictOut(pair=v.pair, verdict=v.verdict, rationale=v.rationale)
            for v in results
        ]
    )


# ---------- Steel-man + What's-missing ----------


class SectionPassOut(BaseModel):
    result_md: str
    error: str | None = None


def _evidence_blob(cards: list[EvidenceCard]) -> str:
    parts: list[str] = []
    for ec in cards:
        cite = ec.citation or {}
        parts.append(
            f"[@src{ec.source_id}] ({cite.get('source_title') or 'source'})\n{ec.quote_text.strip()}"
        )
    return "\n\n".join(parts)


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", text).strip()


async def _section_pass(
    db: AsyncSession,
    user_id: int,
    project_id: int,
    node_id: int,
    runner,
) -> SectionPassOut:
    n = await _own_node(db, user_id, project_id, node_id)
    cards = (
        await db.execute(
            select(EvidenceCard)
            .where(EvidenceCard.outline_node_id == node_id)
            .order_by(EvidenceCard.order_in_node, EvidenceCard.id)
        )
    ).scalars().all()
    try:
        out = await runner(
            section_title=n.title,
            draft_text=_strip_html(n.body_md or ""),
            evidence_blob=_evidence_blob(list(cards)),
        )
    except Exception as e:
        return SectionPassOut(result_md="", error=str(e)[:300])
    return SectionPassOut(result_md=out)


@router.post(
    "/{project_id}/nodes/{node_id}/steel-man",
    response_model=SectionPassOut,
)
async def steel_man(
    project_id: int,
    node_id: int,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> SectionPassOut:
    return await _section_pass(db, user_id, project_id, node_id, steel_man_section)


@router.post(
    "/{project_id}/nodes/{node_id}/whats-missing",
    response_model=SectionPassOut,
)
async def whats_missing(
    project_id: int,
    node_id: int,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> SectionPassOut:
    return await _section_pass(db, user_id, project_id, node_id, whats_missing_section)
