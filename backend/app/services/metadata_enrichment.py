"""Best-effort metadata enrichment via free APIs (OpenLibrary for ISBN, CrossRef for DOI).

Failures are non-fatal — we just return what we already have.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class EnrichedMetadata:
    title: str | None = None
    authors: list[str] | None = None
    year: int | None = None
    publisher: str | None = None
    language: str | None = None
    isbn: str | None = None
    doi: str | None = None


def enrich_by_isbn(isbn: str, timeout: float = 5.0) -> EnrichedMetadata:
    out = EnrichedMetadata(isbn=isbn)
    try:
        r = httpx.get(
            "https://openlibrary.org/api/books",
            params={"bibkeys": f"ISBN:{isbn}", "format": "json", "jscmd": "data"},
            timeout=timeout,
        )
        r.raise_for_status()
        data = r.json().get(f"ISBN:{isbn}")
        if not data:
            return out
        out.title = data.get("title")
        out.authors = [a.get("name") for a in data.get("authors", []) if a.get("name")]
        publishers = data.get("publishers", [])
        if publishers:
            out.publisher = publishers[0].get("name")
        publish_date = data.get("publish_date")
        if publish_date:
            for tok in publish_date.split():
                if tok.isdigit() and len(tok) == 4:
                    out.year = int(tok)
                    break
    except Exception as e:
        logger.warning("openlibrary lookup failed for %s: %s", isbn, e)
    return out


def enrich_by_doi(doi: str, timeout: float = 5.0) -> EnrichedMetadata:
    out = EnrichedMetadata(doi=doi)
    try:
        r = httpx.get(
            f"https://api.crossref.org/works/{doi}",
            timeout=timeout,
            headers={"Accept": "application/json"},
        )
        r.raise_for_status()
        msg = r.json().get("message") or {}
        titles = msg.get("title") or []
        out.title = titles[0] if titles else None
        out.authors = [
            f"{a.get('given', '').strip()} {a.get('family', '').strip()}".strip()
            for a in (msg.get("author") or [])
        ] or None
        date_parts = (msg.get("issued") or {}).get("date-parts") or []
        if date_parts and date_parts[0]:
            out.year = int(date_parts[0][0])
        publisher = msg.get("publisher")
        if publisher:
            out.publisher = publisher
        out.language = msg.get("language")
    except Exception as e:
        logger.warning("crossref lookup failed for %s: %s", doi, e)
    return out
