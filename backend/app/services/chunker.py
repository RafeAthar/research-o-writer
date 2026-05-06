"""Structure-aware chunker.

Groups paragraphs into chunks of ~target_tokens (with overlap), never
crossing a chapter_path boundary. Each chunk preserves citation metadata
from its constituent paragraphs.
"""

from __future__ import annotations

from dataclasses import dataclass

import tiktoken

from app.services.parsers.types import ParsedParagraph

_TOKENIZER = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_TOKENIZER.encode(text, disallowed_special=()))


@dataclass
class Chunk:
    text: str
    chapter_path: list[str]
    page_start: int | None
    page_end: int | None
    paragraph_index: int  # index of the *first* paragraph in this chunk
    char_start: int | None
    char_end: int | None
    token_count: int


def chunk_paragraphs(
    paragraphs: list[ParsedParagraph],
    *,
    target_tokens: int = 500,
    max_tokens: int = 800,
    min_tokens: int = 200,
    overlap_paragraphs: int = 1,
) -> list[Chunk]:
    """Group paragraphs into chunks. Boundaries: chapter_path changes, or token cap."""
    chunks: list[Chunk] = []
    if not paragraphs:
        return chunks

    buf: list[ParsedParagraph] = []
    buf_tokens = 0
    current_path: list[str] | None = None

    def flush() -> None:
        nonlocal buf, buf_tokens
        if not buf:
            return
        text = "\n\n".join(p.text for p in buf)
        chunks.append(
            Chunk(
                text=text,
                chapter_path=list(current_path or []),
                page_start=_first_not_none(p.page_start for p in buf),
                page_end=_last_not_none(p.page_end for p in buf),
                paragraph_index=buf[0].paragraph_index,
                char_start=_first_not_none(p.char_start for p in buf),
                char_end=_last_not_none(p.char_end for p in buf),
                token_count=buf_tokens,
            )
        )
        # Carry overlap into the next chunk: keep the last N paragraphs as a soft tail.
        if overlap_paragraphs > 0 and len(buf) > overlap_paragraphs:
            tail = buf[-overlap_paragraphs:]
            buf = list(tail)
            buf_tokens = sum(count_tokens(p.text) for p in buf)
        else:
            buf = []
            buf_tokens = 0

    for p in paragraphs:
        p_path = p.chapter_path or []
        if current_path is None:
            current_path = p_path
        path_changed = p_path != current_path

        if path_changed and buf_tokens >= min_tokens:
            flush()
            buf = []
            buf_tokens = 0
            current_path = p_path
        elif path_changed:
            # Path changed but chunk too small to flush: still respect boundary.
            flush()
            buf = []
            buf_tokens = 0
            current_path = p_path

        p_tokens = count_tokens(p.text)

        if p_tokens > max_tokens:
            # Oversized paragraph: split it on its own.
            if buf:
                flush()
            for piece in _split_oversized(p, max_tokens):
                chunks.append(piece)
            current_path = p_path
            buf = []
            buf_tokens = 0
            continue

        if buf_tokens + p_tokens > max_tokens:
            flush()
            current_path = p_path

        buf.append(p)
        buf_tokens += p_tokens

        if buf_tokens >= target_tokens:
            flush()
            current_path = p_path

    if buf and buf_tokens >= min_tokens // 4:
        flush()

    return chunks


def _split_oversized(p: ParsedParagraph, max_tokens: int) -> list[Chunk]:
    """Split a single huge paragraph on sentence boundaries."""
    import re

    sentences = re.split(r"(?<=[.!?])\s+", p.text)
    out: list[Chunk] = []
    buf: list[str] = []
    buf_tokens = 0
    char_start = p.char_start or 0

    def flush() -> None:
        nonlocal buf, buf_tokens, char_start
        if not buf:
            return
        text = " ".join(buf).strip()
        out.append(
            Chunk(
                text=text,
                chapter_path=list(p.chapter_path),
                page_start=p.page_start,
                page_end=p.page_end,
                paragraph_index=p.paragraph_index,
                char_start=char_start,
                char_end=char_start + len(text),
                token_count=count_tokens(text),
            )
        )
        char_start += len(text) + 1
        buf = []
        buf_tokens = 0

    for s in sentences:
        s_tokens = count_tokens(s)
        if buf_tokens + s_tokens > max_tokens and buf:
            flush()
        buf.append(s)
        buf_tokens += s_tokens

    flush()
    return out


def _first_not_none(it):
    for v in it:
        if v is not None:
            return v
    return None


def _last_not_none(it):
    last = None
    for v in it:
        if v is not None:
            last = v
    return last
