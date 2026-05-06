from __future__ import annotations

from io import BytesIO

import ebooklib
from bs4 import BeautifulSoup
from ebooklib import epub

from app.services.parsers.html import _parse_soup
from app.services.parsers.types import ParsedDocument, ParsedParagraph, StructureNode


def parse_epub(data: bytes) -> ParsedDocument:
    book = epub.read_epub(BytesIO(data))

    title = (book.get_metadata("DC", "title") or [("",)])[0][0] or None
    authors = [a[0] for a in (book.get_metadata("DC", "creator") or []) if a and a[0]]
    language = (book.get_metadata("DC", "language") or [("",)])[0][0] or None

    paragraphs: list[ParsedParagraph] = []
    structure_root: list[StructureNode] = []
    full_parts: list[str] = []
    char_cursor = 0
    para_idx = 0
    word_count = 0

    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "lxml")
        # Reuse HTML parser logic per chapter document.
        sub = _parse_soup(soup, title=None)

        # Offset paragraph indices and char cursors so they're globally consistent.
        for p in sub.paragraphs:
            new_para = ParsedParagraph(
                text=p.text,
                chapter_path=p.chapter_path,
                paragraph_index=para_idx,
                page_start=None,
                page_end=None,
                char_start=char_cursor,
                char_end=char_cursor + len(p.text),
            )
            paragraphs.append(new_para)
            full_parts.append(p.text)
            char_cursor += len(p.text) + 2
            para_idx += 1
            word_count += len(p.text.split())

        structure_root.extend(sub.structure)

    full_text = "\n\n".join(full_parts)
    return ParsedDocument(
        title=title,
        authors=authors,
        language=(language.split("-")[0] if language else None),
        page_count=None,
        word_count=word_count,
        paragraphs=paragraphs,
        structure=structure_root,
        full_text=full_text,
    )
