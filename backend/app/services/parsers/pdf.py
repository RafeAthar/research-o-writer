from __future__ import annotations

import re
from io import BytesIO

import fitz  # PyMuPDF

from app.services.parsers.types import ParsedDocument, ParsedParagraph, StructureNode

_PARA_SPLIT = re.compile(r"\n\s*\n+")
_WHITESPACE = re.compile(r"[ \t]+")


class ScannedPdfError(Exception):
    """Raised when a PDF appears to have no extractable text (likely scanned)."""


def parse_pdf(data: bytes) -> ParsedDocument:
    doc = fitz.open(stream=BytesIO(data), filetype="pdf")

    md = doc.metadata or {}
    title = md.get("title") or None
    authors_raw = md.get("author") or ""
    authors = [a.strip() for a in re.split(r"[,;]| and ", authors_raw) if a.strip()]
    language = (md.get("language") or "").split("-")[0] or None

    # TOC: list of [level, title, page_1based]
    toc = doc.get_toc(simple=True) or []
    structure_root, page_to_path = _build_structure(toc, page_count=doc.page_count)

    full_text_parts: list[str] = []
    paragraphs: list[ParsedParagraph] = []
    para_idx = 0
    char_cursor = 0
    word_count = 0

    for page_num in range(doc.page_count):
        page = doc.load_page(page_num)
        page_text = page.get_text("text") or ""
        page_text = _normalize(page_text)

        page_1based = page_num + 1
        chapter_path = page_to_path.get(page_1based, [])

        for raw in _PARA_SPLIT.split(page_text):
            t = raw.strip()
            if not t:
                continue
            t = _WHITESPACE.sub(" ", t)
            start = char_cursor
            end = start + len(t)
            paragraphs.append(
                ParsedParagraph(
                    text=t,
                    chapter_path=chapter_path,
                    paragraph_index=para_idx,
                    page_start=page_1based,
                    page_end=page_1based,
                    char_start=start,
                    char_end=end,
                )
            )
            full_text_parts.append(t)
            char_cursor = end + 2  # account for "\n\n" separator
            para_idx += 1
            word_count += len(t.split())

    if not paragraphs:
        raise ScannedPdfError(
            "PDF appears to contain no extractable text (likely scanned). "
            "OCR is not supported in Phase 1."
        )

    full_text = "\n\n".join(full_text_parts)
    return ParsedDocument(
        title=title,
        authors=authors,
        language=language,
        page_count=doc.page_count,
        word_count=word_count,
        paragraphs=paragraphs,
        structure=structure_root,
        full_text=full_text,
    )


def _normalize(text: str) -> str:
    # Join lines that are wrapped within a paragraph (but keep paragraph breaks).
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Common PDF artifact: hyphenated word at line break.
    text = re.sub(r"-\n(?=\w)", "", text)
    # Collapse single newlines inside paragraphs into spaces, preserve double newlines.
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
    return text


def _build_structure(
    toc: list[list], page_count: int
) -> tuple[list[StructureNode], dict[int, list[str]]]:
    """Build a structure tree and a page→chapter_path map."""
    if not toc:
        return [], {}

    roots: list[StructureNode] = []
    stack: list[StructureNode] = []

    # First pass: build tree
    for level, title, page in toc:
        node = StructureNode(
            title=str(title).strip(),
            depth=int(level),
            chapter_path=[],
            page_start=int(page) if page else None,
        )
        while stack and stack[-1].depth >= node.depth:
            stack.pop()
        if stack:
            parent = stack[-1]
            node.chapter_path = [*parent.chapter_path, node.title]
            node.order_in_parent = len(parent.children)
            parent.children.append(node)
        else:
            node.chapter_path = [node.title]
            node.order_in_parent = len(roots)
            roots.append(node)
        stack.append(node)

    # Second pass: assign page_end based on next sibling/parent and build map.
    page_to_path: dict[int, list[str]] = {}
    flat: list[StructureNode] = []
    _flatten(roots, flat)

    for i, node in enumerate(flat):
        next_start = flat[i + 1].page_start if i + 1 < len(flat) else page_count
        node.page_end = (next_start or page_count) - 1 if next_start else page_count

    # Map each page to the deepest chapter_path covering it.
    for node in flat:
        if not node.page_start:
            continue
        end = node.page_end or node.page_start
        for p in range(node.page_start, end + 1):
            existing = page_to_path.get(p, [])
            if len(node.chapter_path) >= len(existing):
                page_to_path[p] = node.chapter_path

    return roots, page_to_path


def _flatten(nodes: list[StructureNode], out: list[StructureNode]) -> None:
    for n in nodes:
        out.append(n)
        _flatten(n.children, out)
