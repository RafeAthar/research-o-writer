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

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal, get_db
from app.deps import require_auth
from app.models.chat import Chat, ChatMessage
from app.models.project import StyleProfile
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


class ChatCreate(BaseModel):
    title: str = "New chat"
    scope: str = Field(default="library", pattern="^(library|sources|project)$")
    source_ids: list[int] = Field(default_factory=list)
    project_id: int | None = None


class ChatOut(BaseModel):
    id: int
    title: str
    scope: str
    source_ids: list[int]
    project_id: int | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    citations: list[dict]
    model: str | None
    error: str | None
    created_at: datetime

    class Config:
        from_attributes = True


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
    return [ChatOut.model_validate(r) for r in rows]


@router.get("/{chat_id}/messages", response_model=list[MessageOut])
async def list_messages(
    chat_id: int,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> list[MessageOut]:
    chat = (
        await db.execute(select(Chat).where(Chat.id == chat_id, Chat.user_id == user_id))
    ).scalar_one_or_none()
    if not chat:
        raise HTTPException(404, "chat not found")
    rows = (
        await db.execute(
            select(ChatMessage).where(ChatMessage.chat_id == chat_id).order_by(ChatMessage.id)
        )
    ).scalars().all()
    return [MessageOut.model_validate(r) for r in rows]


def _sse(event: str, data: str) -> bytes:
    return f"event: {event}\ndata: {data}\n\n".encode()


@router.post("/{chat_id}/messages")
async def post_message(
    chat_id: int,
    body: SendMessage,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    chat = (
        await db.execute(select(Chat).where(Chat.id == chat_id, Chat.user_id == user_id))
    ).scalar_one_or_none()
    if not chat:
        raise HTTPException(404, "chat not found")

    # 1. Persist user message.
    user_msg = ChatMessage(chat_id=chat_id, role="user", content=body.content)
    db.add(user_msg)
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
        try:
            async for delta in gateway.stream_chat(
                system=system_prompt,
                messages=messages,
                mode=body.mode,
                max_tokens=2048,
            ):
                accumulated.append(delta)
                yield _sse("token", json.dumps(delta))
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

        async with SessionLocal() as s:
            s.add(
                ChatMessage(
                    chat_id=chat_id,
                    role="assistant",
                    content=verified.text,
                    citations=used_citations,
                    model=gateway.model_for(body.mode),
                )
            )
            await s.commit()

        done = {
            "text": verified.text,
            "used_passages": verified.used_passages,
            "issues": verified.issues,
            "citations": used_citations,
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
