from __future__ import annotations

import os
import re

from app.services.parsers.types import ParsedDocument, ParsedParagraph, StructureNode

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_PARA_SEP = re.compile(r"\n\s*\n+")


def parse_markdown(
    data: bytes, *, is_markdown: bool = True, filename: str | None = None
) -> ParsedDocument:
    text = data.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")

    title: str | None = None
    paragraphs: list[ParsedParagraph] = []
    structure_root: list[StructureNode] = []
    stack: list[StructureNode] = []
    chapter_path: list[str] = []
    full_parts: list[str] = []
    char_cursor = 0
    para_idx = 0
    word_count = 0

    if is_markdown:
        # Process line-by-line so headings build a structure; paragraphs grouped by blank lines.
        buffer: list[str] = []

        def flush_paragraph() -> None:
            nonlocal char_cursor, para_idx, word_count
            if not buffer:
                return
            joined = " ".join(line.strip() for line in buffer if line.strip())
            buffer.clear()
            if not joined:
                return
            start = char_cursor
            end = start + len(joined)
            paragraphs.append(
                ParsedParagraph(
                    text=joined,
                    chapter_path=list(chapter_path),
                    paragraph_index=para_idx,
                    char_start=start,
                    char_end=end,
                )
            )
            full_parts.append(joined)
            char_cursor = end + 2
            para_idx += 1
            word_count += len(joined.split())

        for line in text.split("\n"):
            m = _HEADING_RE.match(line)
            if m:
                flush_paragraph()
                level = len(m.group(1))
                heading_text = m.group(2).strip()
                if title is None and level == 1:
                    title = heading_text
                node = StructureNode(title=heading_text, depth=level, chapter_path=[])
                while stack and stack[-1].depth >= level:
                    stack.pop()
                if stack:
                    parent = stack[-1]
                    node.chapter_path = [*parent.chapter_path, heading_text]
                    node.order_in_parent = len(parent.children)
                    parent.children.append(node)
                else:
                    node.chapter_path = [heading_text]
                    node.order_in_parent = len(structure_root)
                    structure_root.append(node)
                stack.append(node)
                chapter_path = list(node.chapter_path)
                continue

            if not line.strip():
                flush_paragraph()
                continue
            buffer.append(line)

        flush_paragraph()
    else:
        # Plain text: paragraphs separated by blank lines, no structure.
        for raw in _PARA_SEP.split(text):
            t = raw.strip()
            if not t:
                continue
            t = re.sub(r"\s+", " ", t)
            start = char_cursor
            end = start + len(t)
            paragraphs.append(
                ParsedParagraph(
                    text=t,
                    chapter_path=[],
                    paragraph_index=para_idx,
                    char_start=start,
                    char_end=end,
                )
            )
            full_parts.append(t)
            char_cursor = end + 2
            para_idx += 1
            word_count += len(t.split())

    if title is None and filename:
        title = os.path.splitext(os.path.basename(filename))[0] or None

    full_text = "\n\n".join(full_parts)
    return ParsedDocument(
        title=title,
        authors=[],
        language=None,
        page_count=None,
        word_count=word_count,
        paragraphs=paragraphs,
        structure=structure_root,
        full_text=full_text,
    )
