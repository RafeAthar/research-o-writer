"""Resolve a retrieval scope into a concrete set of source ids.

Three scopes share one resolver so chat and search behave identically:

- ``library``  -> ``None``  : no filter, search the whole library.
- ``sources``  -> the explicit list, or ``None`` if empty.
- ``project``  -> the project's shelf (``project_sources``); an **empty** shelf
  resolves to ``[]`` (search nothing), never a library fallback.

The distinction between ``None`` (unrestricted) and ``[]`` (restricted to
nothing) matters: ``hybrid_search`` treats a falsy ``source_ids`` as "no
filter", so callers must short-circuit on ``[]`` and skip retrieval.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import ProjectSource


async def resolve_source_ids(
    db: AsyncSession,
    *,
    user_id: int,
    scope: str,
    source_ids: list[int] | None,
    project_id: int | None,
) -> list[int] | None:
    """Return the source-id filter for a scope.

    ``None`` means "search everything"; an empty list means "search nothing".
    """
    if scope == "sources":
        return source_ids or None
    if scope == "project":
        if project_id is None:
            return []
        rows = (
            await db.execute(
                select(ProjectSource.source_id).where(
                    ProjectSource.project_id == project_id,
                    ProjectSource.user_id == user_id,
                )
            )
        ).scalars().all()
        return list(rows)
    # "library" (and any unknown scope) -> unrestricted
    return None
