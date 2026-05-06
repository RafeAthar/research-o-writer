from __future__ import annotations

import re
from typing import Iterable

from bs4 import BeautifulSoup, Tag
from readability import Document as Readability

from app.services.parsers.types import ParsedDocument, ParsedParagraph, StructureNode


def parse_html(data: bytes) -> ParsedDocument:
    raw = data.decode("utf-8", errors="replace")
    rd = Readability(raw)
    title = (rd.short_title() or "").strip() or None
    main_html = rd.summary(html_partial=True)
    soup = BeautifulSoup(main_html, "lxml")

    return _parse_soup(soup, title=title)


def _parse_soup(soup: BeautifulSoup, title: str | None) -> ParsedDocument:
    paragraphs: list[ParsedParagraph] = []
    structure_root: list[StructureNode] = []
    stack: list[StructureNode] = []
    chapter_path: list[str] = []
    full_parts: list[str] = []
    char_cursor = 0
    para_idx = 0
    word_count = 0

    for el in _walk(soup):
        tag = el.name
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            level = int(tag[1])
            text = el.get_text(" ", strip=True)
            if not text:
                continue
            node = StructureNode(title=text, depth=level, chapter_path=[])
            while stack and stack[-1].depth >= level:
                stack.pop()
            if stack:
                parent = stack[-1]
                node.chapter_path = [*parent.chapter_path, text]
                node.order_in_parent = len(parent.children)
                parent.children.append(node)
            else:
                node.chapter_path = [text]
                node.order_in_parent = len(structure_root)
                structure_root.append(node)
            stack.append(node)
            chapter_path = list(node.chapter_path)
            continue

        if tag in {"p", "li", "blockquote"}:
            text = el.get_text(" ", strip=True)
            if not text:
                continue
            text = re.sub(r"\s+", " ", text)
            start = char_cursor
            end = start + len(text)
            paragraphs.append(
                ParsedParagraph(
                    text=text,
                    chapter_path=list(chapter_path),
                    paragraph_index=para_idx,
                    page_start=None,
                    page_end=None,
                    char_start=start,
                    char_end=end,
                )
            )
            full_parts.append(text)
            char_cursor = end + 2
            para_idx += 1
            word_count += len(text.split())

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


def _walk(soup: BeautifulSoup) -> Iterable[Tag]:
    for el in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote"]):
        if isinstance(el, Tag):
            yield el
