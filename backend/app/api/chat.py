"""Chat API: streaming, source-grounded, persisted threads.

Three implicit "modes" via scope/source_ids:
- single source: scope="sources", source_ids=[X]
- whole library: scope="library"
- project-attached: scope="project", source_ids derived from project evidence

The streaming endpoint emits Server-Sent Events:
  event: meta            -> JSON with passage citations the model can use
  event: token           -> raw text deltas (data is the delta string)
  event: done            -> final JSON with verified text, used passages, issues
  event: error           -> JSON {"error": "..."}
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal, get_db
from app.deps import require_auth
from app.models.chat import Chat, ChatMessage
from app.models.project import StyleProfile
from app.services.chat_aux import suggest_followups, suggest_title
from app.services.model_gateway import get_gateway
from app.services.rag_prompt import (
    SYSTEM_PROMPT,
    build_user_turn,
    verify_citations,
)
from app.services.search import RetrievedChunk, hybrid_search
from app.services.writing_passes import style_profile_for_prompt

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chats", tags=["chat"])


DEFAULT_TITLES = {"New chat", "Library chat", "Source chat"}


class ChatCreate(BaseModel):
    title: str = "New chat"
    scope: str = Field(default="library", pattern="^(library|sources|project)$")
    source_ids: list[int] = Field(default_factory=list)
    project_id: int | None = None


class ChatPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=512)
    scope: str | None = Field(default=None, pattern="^(library|sources|project)$")
    source_ids: list[int] | None = None
    project_id: int | None = None


class ChatOut(BaseModel):
    id: int
    title: str
    scope: str
    source_ids: list[int]
    project_id: int | None
    created_at: datetime
    updated_at: datetime
    last_message_preview: str | None = None
    message_count: int = 0

    class Config:
        from_attributes = True


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    citations: list[dict]
    suggestions: list[str] | None
    stop_reason: str | None
    model: str | None
    error: str | None
    created_at: datetime

    class Config:
        from_attributes = True


async def _own_chat(db: AsyncSession, user_id: int, chat_id: int) -> Chat:
    chat = (
        await db.execute(select(Chat).where(Chat.id == chat_id, Chat.user_id == user_id))
    ).scalar_one_or_none()
    if not chat:
        raise HTTPException(404, "chat not found")
    return chat


class SendMessage(BaseModel):
    content: str = Field(..., min_length=1)
    mode: str = Field(default="default", pattern="^(default|hard)$")
    k: int = Field(default=10, ge=1, le=30)


@router.post("", response_model=ChatOut, status_code=201)
async def create_chat(
    body: ChatCreate,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> ChatOut:
    chat = Chat(
        user_id=user_id,
        title=body.title,
        scope=body.scope,
        source_ids=body.source_ids,
        project_id=body.project_id,
    )
    db.add(chat)
    await db.commit()
    await db.refresh(chat)
    return ChatOut.model_validate(chat)


@router.get("", response_model=list[ChatOut])
async def list_chats(
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> list[ChatOut]:
    rows = (
        await db.execute(
            select(Chat).where(Chat.user_id == user_id).order_by(Chat.updated_at.desc())
        )
    ).scalars().all()

    chat_ids = [c.id for c in rows]
    counts: dict[int, int] = {}
    previews: dict[int, str] = {}
    if chat_ids:
        count_rows = (
            await db.execute(
                select(ChatMessage.chat_id, func.count(ChatMessage.id))
                .where(ChatMessage.chat_id.in_(chat_ids))
                .group_by(ChatMessage.chat_id)
            )
        ).all()
        counts = {cid: n for cid, n in count_rows}

        # Latest message preview per chat. Use DISTINCT ON for one round trip.
        latest_stmt = (
            select(ChatMessage.chat_id, ChatMessage.content)
            .where(ChatMessage.chat_id.in_(chat_ids))
            .order_by(ChatMessage.chat_id, ChatMessage.id.desc())
            .distinct(ChatMessage.chat_id)
        )
        for cid, content in (await db.execute(latest_stmt)).all():
            previews[cid] = (content or "").strip().replace("\n", " ")[:160]

    out: list[ChatOut] = []
    for c in rows:
        item = ChatOut.model_validate(c)
        item.message_count = counts.get(c.id, 0)
        item.last_message_preview = previews.get(c.id)
        out.append(item)
    return out


@router.get("/{chat_id}", response_model=ChatOut)
async def get_chat(
    chat_id: int,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> ChatOut:
    chat = await _own_chat(db, user_id, chat_id)
    return ChatOut.model_validate(chat)


@router.patch("/{chat_id}", response_model=ChatOut)
async def update_chat(
    chat_id: int,
    body: ChatPatch,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> ChatOut:
    chat = await _own_chat(db, user_id, chat_id)
    if body.title is not None:
        chat.title = body.title
    if body.scope is not None:
        chat.scope = body.scope
    if body.source_ids is not None:
        chat.source_ids = body.source_ids
    if body.project_id is not None:
        chat.project_id = body.project_id
    await db.commit()
    await db.refresh(chat)
    return ChatOut.model_validate(chat)


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(
    chat_id: int,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> None:
    chat = await _own_chat(db, user_id, chat_id)
    await db.delete(chat)
    await db.commit()


@router.get("/{chat_id}/messages", response_model=list[MessageOut])
async def list_messages(
    chat_id: int,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> list[MessageOut]:
    await _own_chat(db, user_id, chat_id)
    rows = (
        await db.execute(
            select(ChatMessage).where(ChatMessage.chat_id == chat_id).order_by(ChatMessage.id)
        )
    ).scalars().all()
    return [MessageOut.model_validate(r) for r in rows]


@router.delete(
    "/{chat_id}/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_message(
    chat_id: int,
    message_id: int,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> None:
    await _own_chat(db, user_id, chat_id)
    msg = (
        await db.execute(
            select(ChatMessage).where(
                ChatMessage.id == message_id, ChatMessage.chat_id == chat_id
            )
        )
    ).scalar_one_or_none()
    if not msg:
        raise HTTPException(404, "message not found")
    await db.delete(msg)
    await db.commit()


def _sse(event: str, data: str) -> bytes:
    return f"event: {event}\ndata: {data}\n\n".encode()


@router.post("/{chat_id}/messages")
async def post_message(
    chat_id: int,
    body: SendMessage,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    chat = await _own_chat(db, user_id, chat_id)

    # First-turn check: drives the optional Haiku auto-title below.
    prior_count = (
        await db.execute(
            select(ChatMessage.id).where(ChatMessage.chat_id == chat_id).limit(1)
        )
    ).first()
    is_first_turn = prior_count is None

    # 1. Persist user message.
    user_msg = ChatMessage(chat_id=chat_id, role="user", content=body.content)
    db.add(user_msg)
    await db.commit()

    # 1b. If this is the first user turn and the chat still has a default
    # title, generate a short one via Haiku. Failures are silent.
    if is_first_turn and chat.title in DEFAULT_TITLES:
        new_title = await suggest_title(body.content)
        if new_title:
            chat.title = new_title
            await db.commit()

    # 2. Retrieve passages.
    source_ids: list[int] | None = chat.source_ids if chat.source_ids else None
    hits = await hybrid_search(
        db,
        user_id=user_id,
        query=body.content,
        k_final=body.k,
        source_ids=source_ids,
    )

    # 3. Build prompt + load conversation history (excluding the freshly-persisted user msg
    # — we'll add it last so the model sees it with the passages attached).
    history_rows = (
        await db.execute(
            select(ChatMessage)
            .where(ChatMessage.chat_id == chat_id, ChatMessage.id < user_msg.id)
            .order_by(ChatMessage.id)
        )
    ).scalars().all()

    messages: list[dict] = []
    for m in history_rows:
        if m.role in ("user", "assistant") and m.content:
            messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": build_user_turn(body.content, hits)})

    # 4. If this chat is project-scoped and a style profile exists, append it
    # to the system prompt so drafts mimic the user's voice.
    system_prompt = SYSTEM_PROMPT
    if chat.project_id:
        sp = (
            await db.execute(
                select(StyleProfile).where(
                    StyleProfile.user_id == user_id,
                    StyleProfile.project_id == chat.project_id,
                )
            )
        ).scalar_one_or_none()
        if sp and sp.profile_md:
            system_prompt = system_prompt + style_profile_for_prompt(sp.profile_md)

    gateway = get_gateway()

    async def event_stream():
        # Emit meta with the passages we fed the model so the frontend can render
        # the citation cards immediately.
        meta = {
            "passages": [
                {
                    "id": i + 1,
                    "chunk_id": h.chunk_id,
                    "source_id": h.source_id,
                    "source_title": h.source_title,
                    "chapter_path": h.chapter_path,
                    "page_start": h.page_start,
                    "page_end": h.page_end,
                    "paragraph_index": h.paragraph_index,
                    "char_start": h.char_start,
                    "char_end": h.char_end,
                    "score": h.score,
                    "preview": h.text[:400],
                }
                for i, h in enumerate(hits)
            ]
        }
        yield _sse("meta", json.dumps(meta))

        accumulated: list[str] = []
        stop_reason: str | None = None
        try:
            async for ev in gateway.stream_chat(
                system=system_prompt,
                messages=messages,
                mode=body.mode,
                max_tokens=2048,
            ):
                if ev.kind == "delta":
                    accumulated.append(ev.text)
                    yield _sse("token", json.dumps(ev.text))
                else:  # "done"
                    stop_reason = ev.stop_reason
        except asyncio.CancelledError:
            # Client closed the SSE connection (Stop button). Persist whatever
            # we produced so the user can resume / regenerate, then re-raise so
            # the ASGI server cleans up.
            async with SessionLocal() as s:
                s.add(
                    ChatMessage(
                        chat_id=chat_id,
                        role="assistant",
                        content="".join(accumulated),
                        citations=[],
                        stop_reason="client_abort",
                        model=gateway.model_for(body.mode),
                    )
                )
                await s.commit()
            raise
        except Exception as e:
            logger.exception("model stream failed")
            err_text = str(e)[:500]
            yield _sse("error", json.dumps({"error": err_text}))
            # Persist assistant message with error.
            async with SessionLocal() as s:
                s.add(
                    ChatMessage(
                        chat_id=chat_id,
                        role="assistant",
                        content="".join(accumulated),
                        citations=[],
                        stop_reason="error",
                        model=gateway.model_for(body.mode),
                        error=err_text,
                    )
                )
                await s.commit()
            return

        full = "".join(accumulated)
        verified = verify_citations(full, n_passages=len(hits))

        used_citations = [
            _passage_citation(hits[i - 1], passage_number=i) for i in verified.used_passages
        ]

        # Best-effort follow-up suggestions. Skipped on max_tokens cutoff
        # (the answer isn't complete enough to suggest follow-ups against).
        followups: list[str] = []
        if stop_reason != "max_tokens" and verified.text:
            followups = await suggest_followups(body.content, verified.text)

        async with SessionLocal() as s:
            s.add(
                ChatMessage(
                    chat_id=chat_id,
                    role="assistant",
                    content=verified.text,
                    citations=used_citations,
                    suggestions=followups or None,
                    stop_reason=stop_reason,
                    model=gateway.model_for(body.mode),
                )
            )
            await s.commit()

        done = {
            "text": verified.text,
            "used_passages": verified.used_passages,
            "issues": verified.issues,
            "citations": used_citations,
            "suggestions": followups,
            "stop_reason": stop_reason,
        }
        yield _sse("done", json.dumps(done))
        await asyncio.sleep(0)  # let buffers flush

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _passage_citation(h: RetrievedChunk, *, passage_number: int) -> dict:
    return {
        "passage": passage_number,
        "chunk_id": h.chunk_id,
        "source_id": h.source_id,
        "source_title": h.source_title,
        "chapter_path": h.chapter_path,
        "page_start": h.page_start,
        "page_end": h.page_end,
        "paragraph_index": h.paragraph_index,
        "char_start": h.char_start,
        "char_end": h.char_end,
        "preview": h.text[:400],
    }
