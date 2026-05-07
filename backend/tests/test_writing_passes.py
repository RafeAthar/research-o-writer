"""Unit tests for the LLM-pass helpers (style profile injection + verdict parsing).

We don't call the model here; we just exercise pure logic.
"""

from app.services.writing_passes import (
    _parse_verdicts,
    style_profile_for_prompt,
)


def test_style_profile_empty_returns_empty_string():
    assert style_profile_for_prompt("") == ""
    assert style_profile_for_prompt("   ") == ""


def test_style_profile_wraps_with_markers():
    out = style_profile_for_prompt("Plain prose. Short sentences.")
    assert "VOICE PROFILE" in out
    assert "Plain prose. Short sentences." in out
    assert out.startswith("\n\n")


def test_parse_verdicts_handles_clean_json():
    raw = (
        '{"verdicts": ['
        '{"pair": [1, 2], "verdict": "agree", "rationale": "Both endorse X."},'
        '{"pair": [1, 3], "verdict": "disagree", "rationale": "One denies."}'
        "]}"
    )
    out = _parse_verdicts(raw)
    assert len(out) == 2
    assert out[0].pair == (1, 2)
    assert out[0].verdict == "agree"
    assert out[1].verdict == "disagree"


def test_parse_verdicts_strips_code_fences():
    raw = '```json\n{"verdicts": [{"pair":[1,2],"verdict":"unrelated","rationale":""}]}\n```'
    out = _parse_verdicts(raw)
    assert len(out) == 1
    assert out[0].verdict == "unrelated"


def test_parse_verdicts_returns_empty_on_garbage():
    assert _parse_verdicts("hi there") == []


def test_parse_verdicts_skips_malformed_entries():
    raw = (
        '{"verdicts": ['
        '{"pair": [1, 2], "verdict": "agree", "rationale": "ok"},'
        '{"pair": "bad", "verdict": "agree"},'
        '{"verdict": "agree"}'
        "]}"
    )
    out = _parse_verdicts(raw)
    assert len(out) == 1
    assert out[0].pair == (1, 2)
