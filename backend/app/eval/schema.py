"""Eval-set schema. Kept loose so that human-edited JSON forgives missing
optional fields.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EvalEntry:
    id: str
    query: str
    expected: str | None  # "no_answer" or None
    expected_source_title: str | None
    expected_chapter_path: list[str] | None
    expected_text_substring: str | None

    @classmethod
    def from_dict(cls, d: dict) -> "EvalEntry":
        return cls(
            id=d["id"],
            query=d["query"],
            expected=d.get("expected"),
            expected_source_title=d.get("expected_source_title"),
            expected_chapter_path=d.get("expected_chapter_path"),
            expected_text_substring=d.get("expected_text_substring"),
        )

    @property
    def is_no_answer(self) -> bool:
        return self.expected == "no_answer"
