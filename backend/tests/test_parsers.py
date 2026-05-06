from app.models.source import SourceFormat
from app.services.parsers import parse


def test_parse_markdown_builds_structure_and_paragraphs() -> None:
    md = b"""# My Book

Intro paragraph.

## Chapter 1

First para of ch1.

Second para of ch1.

## Chapter 2

Para of ch2.
"""
    doc = parse(SourceFormat.MARKDOWN, md, filename="my-book.md")
    assert doc.title == "My Book"
    assert len(doc.structure) == 1
    root = doc.structure[0]
    assert root.title == "My Book"
    titles = [child.title for child in root.children]
    assert "Chapter 1" in titles
    assert "Chapter 2" in titles
    paths = [tuple(p.chapter_path) for p in doc.paragraphs]
    assert any("Chapter 1" in path for path in paths)
    assert any("Chapter 2" in path for path in paths)


def test_parse_text_no_structure() -> None:
    text = b"First paragraph.\n\nSecond paragraph.\n"
    doc = parse(SourceFormat.TEXT, text, filename="notes.txt")
    assert doc.structure == []
    assert len(doc.paragraphs) == 2
