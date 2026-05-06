"""Unit tests for the scoring logic. Mocks hybrid_search so no DB is required."""

import pytest

from app.eval.runner import EvalReport, _score_retrieval, _looks_like_refusal
from app.eval.schema import EvalEntry
from app.services.search import RetrievedChunk


def _hit(title: str, text: str, score: float = 0.5) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=hash(text) & 0xFFFF,
        source_id=1,
        source_title=title,
        chapter_path=[],
        page_start=None,
        page_end=None,
        paragraph_index=None,
        char_start=None,
        char_end=None,
        text=text,
        score=score,
    )


@pytest.mark.asyncio
async def test_score_retrieval_top1_hit():
    e = EvalEntry.from_dict(
        {
            "id": "x",
            "query": "q",
            "expected_source_title": "Flow",
            "expected_text_substring": "balance between challenge and skill",
        }
    )
    hits = [_hit("Flow", "The single most cited condition is the balance between challenge and skill.")]
    res = await _score_retrieval(e, hits, k=10)
    assert res.retrieval_top1
    assert res.retrieval_top5
    assert res.retrieval_topk
    assert res.source_correct_topk


@pytest.mark.asyncio
async def test_score_retrieval_top5_only():
    e = EvalEntry.from_dict(
        {
            "id": "x",
            "query": "q",
            "expected_source_title": "Flow",
            "expected_text_substring": "directed graph",
        }
    )
    # Top-1 is unrelated; the match shows up at position 4.
    hits = [
        _hit("Flow", "irrelevant"),
        _hit("Other", "irrelevant"),
        _hit("Flow", "irrelevant"),
        _hit("Flow", "structure is closer to a directed graph than a hierarchy."),
        _hit("Flow", "irrelevant"),
    ]
    res = await _score_retrieval(e, hits, k=10)
    assert not res.retrieval_top1
    assert res.retrieval_top5
    assert res.source_correct_topk


@pytest.mark.asyncio
async def test_score_retrieval_no_answer_skipped():
    e = EvalEntry.from_dict({"id": "x", "query": "q", "expected": "no_answer"})
    hits = [_hit("Flow", "anything")]
    res = await _score_retrieval(e, hits, k=10)
    assert res.is_no_answer
    assert not res.retrieval_top1
    assert not res.source_correct_topk


def test_refusal_hint_detection():
    assert _looks_like_refusal("The provided sources do not address this directly.")
    assert _looks_like_refusal("I cannot answer based on the provided passages.")
    assert not _looks_like_refusal("The minimum wage in California is $16/hour [P1].")


def test_report_summary_renders_percentages():
    report = EvalReport(
        k=10,
        with_chat=False,
        entries=[],
    )
    text = report.summary()
    assert "Eval report" in text
    assert "Recall@1" in text
