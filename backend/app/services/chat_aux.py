"""Ancillary Haiku-powered helpers for the chat surface.

These are best-effort: every entry point catches exceptions and returns a
fallback so a hiccup in the auxiliary model never blocks the primary
response stream.
"""

from __future__ import annotations

import json
import logging
import re

from app.services.model_gateway import get_gateway

logger = logging.getLogger(__name__)

_TITLE_SYSTEM = (
    "You name research-chat threads. Given a user's first question, return a "
    "concise 4-8 word title that captures the *topic*, not the speaker. "
    "No quotes, no trailing punctuation, no 'Chat about', no 'Question on'. "
    "Title Case is fine. Reply with the title only."
)

_FOLLOWUPS_SYSTEM = (
    "You suggest follow-up questions for a research assistant. Given the user's "
    "question and the assistant's grounded answer, propose exactly 3 short "
    "follow-ups (under 12 words each) that probe deeper, surface tensions, or "
    "ask for evidence the answer didn't cover. Reply ONLY with a JSON array of "
    "3 strings — no prose, no markdown."
)


async def suggest_title(question: str) -> str | None:
    """Return a short title for a new chat, or None on failure."""
    try:
        text = await get_gateway().complete_fast(
            system=_TITLE_SYSTEM,
            prompt=question[:1000],
            max_tokens=32,
        )
    except Exception:
        logger.exception("auto-title generation failed")
        return None
    return _clean_title(text)


def _clean_title(text: str) -> str | None:
    t = text.strip().strip('"').strip("'").rstrip(".!?")
    # Strip a stray leading "Title:" if Haiku adds one.
    t = re.sub(r"^(Title|Topic)\s*[:\-]\s*", "", t, flags=re.IGNORECASE)
    if not t or len(t) > 120:
        return None
    return t


async def suggest_followups(question: str, answer: str) -> list[str]:
    """Return up to 3 follow-up questions. Empty list on failure."""
    if not answer.strip():
        return []
    prompt = (
        f"User question:\n{question[:1000]}\n\n"
        f"Assistant answer:\n{answer[:3000]}\n\n"
        f"Three follow-ups (JSON array):"
    )
    try:
        text = await get_gateway().complete_fast(
            system=_FOLLOWUPS_SYSTEM,
            prompt=prompt,
            max_tokens=200,
        )
    except Exception:
        logger.exception("follow-up suggestion generation failed")
        return []
    return _parse_followups(text)


def _parse_followups(text: str) -> list[str]:
    # Find the first JSON array in the response; tolerate stray prose.
    match = re.search(r"\[.*?\]", text, flags=re.DOTALL)
    if not match:
        return []
    try:
        arr = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    out: list[str] = []
    for item in arr:
        if isinstance(item, str):
            s = item.strip()
            if s and len(s) <= 200:
                out.append(s)
    return out[:3]
