"""Strict-RAG prompt construction and citation verification.

Every model claim must reference one of the numbered passages we provide.
Unsupported claims are flagged after the fact; fabricated citations
([P99] when only P1..P5 were sent) are stripped from the output and
returned as "issues".
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.search import RetrievedChunk

CITATION_RE = re.compile(r"\[P(\d+)(?:,\s*P(\d+))*\]")
SINGLE_CITE_RE = re.compile(r"\[P(\d+)\]")


SYSTEM_PROMPT = """You are a research assistant grounded in the user's private library of books and articles.

You will be given a set of numbered passages from the user's library, each labelled [P1], [P2], etc. Each passage carries full citation metadata (book title, chapter path, and page range).

Your job:

1. Answer the user's question using ONLY information from the provided passages.
2. Cite EVERY substantive claim with the bracket id of the supporting passage(s), e.g. [P1] or [P2, P5].
3. If the passages do not contain enough information to answer confidently, say so clearly. Do not improvise outside the passages. It is fine to answer "the provided sources don't address this directly".
4. When you quote a passage verbatim, put it in quotation marks and follow with its citation.
5. Distinguish:
   - "EXTRACTIVE" claims: directly supported by, or quoting from, a specific passage.
   - "SYNTHETIC" claims: your own synthesis or inference across multiple passages.
   You don't need to label these explicitly, but lean toward extractive when the passages permit it.
6. Be concise. Prefer short, well-cited paragraphs over long unsupported prose.
7. Do not refer to the passage numbers (e.g. "passage P3") in the prose; just append [P3] as a citation.
"""


def build_passages_block(hits: list[RetrievedChunk]) -> str:
    """Render hits as a numbered block for the model context."""
    lines: list[str] = []
    for i, h in enumerate(hits, start=1):
        chap = " > ".join(h.chapter_path) if h.chapter_path else ""
        page_part = ""
        if h.page_start is not None:
            page_part = (
                f", p. {h.page_start}"
                if h.page_end in (None, h.page_start)
                else f", pp. {h.page_start}-{h.page_end}"
            )
        header = f"[P{i}] {h.source_title}"
        if chap:
            header += f" — {chap}"
        if page_part:
            header += page_part
        lines.append(header)
        lines.append(h.text.strip())
        lines.append("")
    return "\n".join(lines).rstrip()


def build_user_turn(question: str, hits: list[RetrievedChunk]) -> str:
    if not hits:
        return f"User question:\n{question}\n\n(No supporting passages were found in the library.)"
    return (
        "Passages:\n\n"
        f"{build_passages_block(hits)}\n\n"
        f"User question:\n{question}"
    )


@dataclass
class VerifiedAnswer:
    text: str
    used_passages: list[int]  # 1-based passage numbers actually cited
    issues: list[str]


def verify_citations(text: str, n_passages: int) -> VerifiedAnswer:
    """Strip fabricated citations and report which were used."""
    issues: list[str] = []
    used: set[int] = set()

    def _replace(m: re.Match) -> str:
        valid_ids: list[str] = []
        for grp in m.groups():
            if grp is None:
                continue
            i = int(grp)
            if 1 <= i <= n_passages:
                valid_ids.append(f"P{i}")
                used.add(i)
            else:
                issues.append(f"fabricated citation [P{i}] removed")
        if not valid_ids:
            return ""
        return "[" + ", ".join(valid_ids) + "]"

    cleaned = CITATION_RE.sub(_replace, text)
    # Also pick up any stray single [P\d+] missed by the multi-pattern.
    def _single(m: re.Match) -> str:
        i = int(m.group(1))
        if 1 <= i <= n_passages:
            used.add(i)
            return m.group(0)
        issues.append(f"fabricated citation [P{i}] removed")
        return ""

    cleaned = SINGLE_CITE_RE.sub(_single, cleaned)

    return VerifiedAnswer(text=cleaned, used_passages=sorted(used), issues=issues)
