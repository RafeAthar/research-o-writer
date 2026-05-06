"""Eval runner: scores retrieval and (optionally) chat against an eval set.

Retrieval scoring (no API key needed):
- Recall@K against `expected_text_substring`: did any top-K hit contain the phrase?
- Source-correctness@K: did any top-K hit come from `expected_source_title`?

Chat scoring (requires ANTHROPIC_API_KEY):
- Citation-source correctness: among the model's verified citations, did at
  least one come from `expected_source_title`?
- Refusal correctness on `no_answer` entries: did the model decline rather
  than fabricate?
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from app.config import get_settings
from app.db import SessionLocal
from app.eval.schema import EvalEntry
from app.services.rag_prompt import (
    SYSTEM_PROMPT,
    build_user_turn,
    verify_citations,
)
from app.services.search import RetrievedChunk, hybrid_search

# Substrings that, when present in a model answer to a no_answer question,
# count as a correct refusal. Conservative on purpose.
_REFUSAL_HINTS = (
    "do not address",
    "does not address",
    "do not contain",
    "does not contain",
    "no information",
    "not enough information",
    "not addressed",
    "not in the provided",
    "sources don't",
    "sources do not",
    "cannot answer",
    "can't answer",
    "unable to answer",
    "the provided sources",
)


@dataclass
class EntryResult:
    id: str
    query: str
    is_no_answer: bool
    retrieval_top1: bool = False
    retrieval_top5: bool = False
    retrieval_topk: bool = False
    source_correct_topk: bool = False
    chat_text: str | None = None
    chat_citation_source_correct: bool | None = None
    chat_refusal_correct: bool | None = None
    notes: list[str] = field(default_factory=list)


@dataclass
class EvalReport:
    k: int
    with_chat: bool
    entries: list[EntryResult]

    def _pct(self, num: int, den: int) -> str:
        if den == 0:
            return "n/a"
        return f"{num}/{den} ({100 * num / den:.0f}%)"

    def summary(self) -> str:
        in_scope = [e for e in self.entries if not e.is_no_answer]
        no_ans = [e for e in self.entries if e.is_no_answer]
        lines = [
            f"=== Eval report (k={self.k}, chat={'on' if self.with_chat else 'off'}) ===",
            f"Total entries: {len(self.entries)}  in-scope: {len(in_scope)}  no-answer: {len(no_ans)}",
            "",
            "Retrieval (in-scope only):",
            f"  Recall@1     {self._pct(sum(e.retrieval_top1 for e in in_scope), len(in_scope))}",
            f"  Recall@5     {self._pct(sum(e.retrieval_top5 for e in in_scope), len(in_scope))}",
            f"  Recall@{self.k:<5}{self._pct(sum(e.retrieval_topk for e in in_scope), len(in_scope))}",
            f"  Source@{self.k:<5}{self._pct(sum(e.source_correct_topk for e in in_scope), len(in_scope))}",
        ]
        if self.with_chat:
            cite_in_scope = [e for e in in_scope if e.chat_citation_source_correct is not None]
            refusal = [e for e in no_ans if e.chat_refusal_correct is not None]
            lines += [
                "",
                "Chat:",
                f"  Citation source@{self.k:<2}{self._pct(sum(bool(e.chat_citation_source_correct) for e in cite_in_scope), len(cite_in_scope))}",
                f"  Refusal correct  {self._pct(sum(bool(e.chat_refusal_correct) for e in refusal), len(refusal))}",
            ]
        lines.append("")
        lines.append("Per-entry detail:")
        for e in self.entries:
            tag = "no-ans" if e.is_no_answer else "scope "
            r = " ".join(
                [
                    f"@1={'Y' if e.retrieval_top1 else '.'}",
                    f"@5={'Y' if e.retrieval_top5 else '.'}",
                    f"@k={'Y' if e.retrieval_topk else '.'}",
                    f"src={'Y' if e.source_correct_topk else '.'}",
                ]
            )
            chat = ""
            if self.with_chat:
                if e.is_no_answer:
                    chat = f"  refuse={'Y' if e.chat_refusal_correct else 'N'}"
                else:
                    chat = f"  cite={'Y' if e.chat_citation_source_correct else 'N'}"
            lines.append(f"  [{tag}] {e.id:<32}  {r}{chat}")
        return "\n".join(lines)


def _hit_matches_substring(hit: RetrievedChunk, needle: str) -> bool:
    return needle.lower() in (hit.text or "").lower()


def _hit_matches_source(hit: RetrievedChunk, title: str) -> bool:
    return (hit.source_title or "").strip().lower() == title.strip().lower()


def _looks_like_refusal(text: str) -> bool:
    t = (text or "").lower()
    return any(p in t for p in _REFUSAL_HINTS)


async def _score_retrieval(
    entry: EvalEntry, hits: list[RetrievedChunk], k: int
) -> EntryResult:
    res = EntryResult(id=entry.id, query=entry.query, is_no_answer=entry.is_no_answer)
    if entry.is_no_answer:
        return res

    needle = entry.expected_text_substring
    if needle:
        res.retrieval_top1 = bool(hits) and _hit_matches_substring(hits[0], needle)
        res.retrieval_top5 = any(_hit_matches_substring(h, needle) for h in hits[:5])
        res.retrieval_topk = any(_hit_matches_substring(h, needle) for h in hits[:k])
    else:
        res.notes.append("no expected_text_substring; skipping recall scoring")

    if entry.expected_source_title:
        res.source_correct_topk = any(
            _hit_matches_source(h, entry.expected_source_title) for h in hits[:k]
        )
    return res


async def run_eval(
    entries: list[EvalEntry],
    *,
    k: int = 10,
    with_chat: bool = False,
) -> EvalReport:
    settings = get_settings()
    user_id = settings.app_default_user_id
    results: list[EntryResult] = []

    if with_chat:
        # Imported lazily so the retrieval-only path needs no anthropic key.
        from app.services.model_gateway import get_gateway

        gateway = get_gateway()
    else:
        gateway = None

    async with SessionLocal() as db:
        for entry in entries:
            hits = await hybrid_search(
                db, user_id=user_id, query=entry.query, k_final=k
            )
            res = await _score_retrieval(entry, hits, k)

            if with_chat and gateway is not None:
                user_turn = build_user_turn(entry.query, hits)
                try:
                    answer = await gateway.complete(
                        system=SYSTEM_PROMPT,
                        messages=[{"role": "user", "content": user_turn}],
                        max_tokens=512,
                    )
                except Exception as e:  # pragma: no cover — network failure path
                    res.notes.append(f"chat call failed: {e}")
                    results.append(res)
                    continue

                verified = verify_citations(answer, n_passages=len(hits))
                res.chat_text = verified.text

                if entry.is_no_answer:
                    res.chat_refusal_correct = _looks_like_refusal(verified.text)
                else:
                    cited_sources = {
                        hits[i - 1].source_title.strip().lower()
                        for i in verified.used_passages
                        if 1 <= i <= len(hits)
                    }
                    target = (entry.expected_source_title or "").strip().lower()
                    res.chat_citation_source_correct = bool(
                        target and target in cited_sources
                    )
            results.append(res)

    return EvalReport(k=k, with_chat=with_chat, entries=results)


def run_eval_sync(
    entries: list[EvalEntry],
    *,
    k: int = 10,
    with_chat: bool = False,
) -> EvalReport:
    return asyncio.run(run_eval(entries, k=k, with_chat=with_chat))
