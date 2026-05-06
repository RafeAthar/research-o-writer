from __future__ import annotations

import os

from app.models.source import SourceFormat
from app.services.parsers.types import ParsedDocument


class UnsupportedFormatError(Exception):
    pass


_EXT_MAP = {
    ".pdf": SourceFormat.PDF,
    ".docx": SourceFormat.DOCX,
    ".epub": SourceFormat.EPUB,
    ".html": SourceFormat.HTML,
    ".htm": SourceFormat.HTML,
    ".md": SourceFormat.MARKDOWN,
    ".markdown": SourceFormat.MARKDOWN,
    ".txt": SourceFormat.TEXT,
}


def detect_format(filename: str | None, content_type: str | None) -> SourceFormat:
    if filename:
        _, ext = os.path.splitext(filename.lower())
        if ext in _EXT_MAP:
            return _EXT_MAP[ext]
    if content_type:
        ct = content_type.lower()
        if "pdf" in ct:
            return SourceFormat.PDF
        if "wordprocessingml" in ct or ct == "application/msword":
            return SourceFormat.DOCX
        if "epub" in ct:
            return SourceFormat.EPUB
        if "html" in ct:
            return SourceFormat.HTML
        if "markdown" in ct:
            return SourceFormat.MARKDOWN
        if ct.startswith("text/"):
            return SourceFormat.TEXT
    raise UnsupportedFormatError(
        f"could not detect format from filename={filename!r} content_type={content_type!r}"
    )


def parse(fmt: SourceFormat, data: bytes, filename: str | None = None) -> ParsedDocument:
    """Dispatch to the right parser. Imports are lazy so unrelated deps don't load."""
    if fmt == SourceFormat.PDF:
        from app.services.parsers.pdf import parse_pdf

        return parse_pdf(data)
    if fmt == SourceFormat.DOCX:
        from app.services.parsers.docx import parse_docx

        return parse_docx(data)
    if fmt == SourceFormat.EPUB:
        from app.services.parsers.epub import parse_epub

        return parse_epub(data)
    if fmt == SourceFormat.HTML:
        from app.services.parsers.html import parse_html

        return parse_html(data)
    if fmt in (SourceFormat.MARKDOWN, SourceFormat.TEXT):
        from app.services.parsers.markdown import parse_markdown

        return parse_markdown(data, is_markdown=fmt == SourceFormat.MARKDOWN, filename=filename)
    raise UnsupportedFormatError(f"no parser for format {fmt}")
