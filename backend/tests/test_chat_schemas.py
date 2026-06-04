"""Validation tests for chat request models.

End-to-end CRUD is exercised manually against a running stack — the rest of
this test suite follows the same boundary (see test_auth.py and the
pure-function tests in test_export.py / test_rag_prompt.py).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.api.chat import ChatCreate, ChatPatch, SendMessage


def test_chat_create_defaults():
    c = ChatCreate()
    assert c.title == "New chat"
    assert c.scope == "library"
    assert c.source_ids == []
    assert c.project_id is None


def test_chat_create_rejects_bad_scope():
    with pytest.raises(ValidationError):
        ChatCreate(scope="everything")


def test_chat_patch_all_optional():
    p = ChatPatch()
    assert p.title is None
    assert p.scope is None
    assert p.source_ids is None
    assert p.project_id is None


def test_chat_patch_rejects_empty_title():
    with pytest.raises(ValidationError):
        ChatPatch(title="")


def test_chat_patch_rejects_bad_scope():
    with pytest.raises(ValidationError):
        ChatPatch(scope="nope")


def test_chat_patch_accepts_partial():
    p = ChatPatch(title="renamed")
    assert p.title == "renamed"
    assert p.scope is None


def test_send_message_k_bounds():
    assert SendMessage(content="hi", k=1).k == 1
    assert SendMessage(content="hi", k=30).k == 30
    with pytest.raises(ValidationError):
        SendMessage(content="hi", k=0)
    with pytest.raises(ValidationError):
        SendMessage(content="hi", k=31)


def test_send_message_mode_pattern():
    assert SendMessage(content="hi").mode == "default"
    assert SendMessage(content="hi", mode="hard").mode == "hard"
    with pytest.raises(ValidationError):
        SendMessage(content="hi", mode="extreme")


def test_send_message_requires_content():
    with pytest.raises(ValidationError):
        SendMessage(content="")
