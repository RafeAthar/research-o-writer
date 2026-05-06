from app.services.rag_prompt import (
    build_passages_block,
    build_user_turn,
    verify_citations,
)
from app.services.search import RetrievedChunk


def _hit(idx: int, title: str, text: str = "Some passage text.") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=100 + idx,
        source_id=10 + idx,
        source_title=title,
        chapter_path=["Part I", f"Chapter {idx}"],
        page_start=10 * idx,
        page_end=10 * idx + 1,
        paragraph_index=idx * 3,
        char_start=0,
        char_end=len(text),
        text=text,
        score=0.5,
    )


def test_passages_block_renders_citation_headers() -> None:
    hits = [_hit(1, "Flow"), _hit(2, "Drive")]
    block = build_passages_block(hits)
    assert "[P1] Flow" in block
    assert "Part I > Chapter 1" in block
    assert "[P2] Drive" in block


def test_build_user_turn_with_no_hits_says_so() -> None:
    out = build_user_turn("What is creativity?", [])
    assert "No supporting passages" in out


def test_verify_citations_strips_fabricated() -> None:
    text = "Creativity emerges from incubation [P1]. Some authors disagree [P9]."
    v = verify_citations(text, n_passages=3)
    assert "[P1]" in v.text
    assert "[P9]" not in v.text
    assert v.used_passages == [1]
    assert any("P9" in i for i in v.issues)


def test_verify_citations_keeps_multi_citation_groups() -> None:
    text = "Both authors agree [P1, P2]."
    v = verify_citations(text, n_passages=3)
    assert "[P1, P2]" in v.text
    assert v.used_passages == [1, 2]
    assert v.issues == []


def test_verify_citations_drops_invalid_in_group() -> None:
    text = "Mixed group [P1, P9]."
    v = verify_citations(text, n_passages=3)
    assert "[P1]" in v.text
    assert "P9" not in v.text
    assert v.used_passages == [1]
    assert any("P9" in i for i in v.issues)
