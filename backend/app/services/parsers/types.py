from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StructureNode:
    title: str
    depth: int
    chapter_path: list[str]
    page_start: int | None = None
    page_end: int | None = None
    order_in_parent: int = 0
    children: list[StructureNode] = field(default_factory=list)


@dataclass
class ParsedParagraph:
    text: str
    chapter_path: list[str]
    paragraph_index: int
    page_start: int | None = None
    page_end: int | None = None
    char_start: int | None = None
    char_end: int | None = None


@dataclass
class ParsedDocument:
    title: str | None
    authors: list[str]
    language: str | None
    page_count: int | None
    word_count: int | None
    paragraphs: list[ParsedParagraph]
    structure: list[StructureNode]
    full_text: str
