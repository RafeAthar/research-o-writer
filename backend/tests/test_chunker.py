from app.services.chunker import chunk_paragraphs, count_tokens
from app.services.parsers.types import ParsedParagraph


def _para(idx: int, text: str, path: list[str]) -> ParsedParagraph:
    return ParsedParagraph(
        text=text,
        chapter_path=path,
        paragraph_index=idx,
        page_start=1,
        page_end=1,
        char_start=idx * 100,
        char_end=idx * 100 + len(text),
    )


def test_chunker_groups_paragraphs_within_chapter() -> None:
    paras = [_para(i, f"Sentence {i}. " * 30, ["Ch1"]) for i in range(6)]
    chunks = chunk_paragraphs(paras, target_tokens=200, max_tokens=400, min_tokens=50)
    assert len(chunks) >= 1
    for c in chunks:
        assert c.chapter_path == ["Ch1"]
        assert c.token_count <= 400
    assert chunks[0].page_start == 1


def test_chunker_respects_chapter_boundary() -> None:
    paras = [
        _para(0, "Alpha. " * 50, ["Ch1"]),
        _para(1, "Beta. " * 50, ["Ch1"]),
        _para(2, "Gamma. " * 50, ["Ch2"]),
        _para(3, "Delta. " * 50, ["Ch2"]),
    ]
    chunks = chunk_paragraphs(paras, target_tokens=300, max_tokens=600, min_tokens=20)
    paths = {tuple(c.chapter_path) for c in chunks}
    assert ("Ch1",) in paths
    assert ("Ch2",) in paths
    # No chunk should span both chapters.
    for c in chunks:
        assert tuple(c.chapter_path) in paths


def test_count_tokens_reasonable() -> None:
    assert count_tokens("hello world") <= 4
    assert count_tokens("") == 0
