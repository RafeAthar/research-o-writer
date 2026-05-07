"""LLM-driven writing passes: style memory, contradiction, steel-man, gap finder.

Each function builds a prompt and calls the model gateway. Pure I/O; no DB.
The API layer is responsible for fetching the inputs (evidence, draft, samples)
and for persisting any generated profile.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from app.services.model_gateway import Mode  # noqa: F401

# Local alias so this module can be imported without the anthropic SDK installed
# (e.g. for unit tests of pure helpers). The runtime import of the gateway is
# deferred into the functions that actually call the model.
Mode = Literal["default", "hard"]  # type: ignore[misc,assignment]

logger = logging.getLogger(__name__)


STYLE_PROFILE_SYSTEM = """You distil a writer's voice into a compact style guide.

Read the samples and produce a Markdown style profile that another model can
follow. Cover at most:
- Tone & register (e.g. plain, technical, conversational, formal).
- Sentence rhythm (short/long mix, fragments, parallelism).
- Diction (favoured words; words to avoid).
- Structure (paragraph length, transitions, opening/closing patterns).
- Idiosyncrasies you can spot (punctuation, repetition, framing devices).

Keep it under 400 words. Do not summarise the content of the samples.
Return only the Markdown profile, no preamble.
"""


CONTRADICTION_SYSTEM = """You are an evidence reconciliation assistant.

You receive a list of pinned quotations (each with an id, source title, and
text) drawn from a single section of a writing project. Decide for every pair
whether they AGREE, DISAGREE, are UNRELATED, or are UNCLEAR (insufficient
information to decide).

Return a single JSON object of the form:
{"verdicts": [
  {"pair": [<id_a>, <id_b>], "verdict": "agree|disagree|unrelated|unclear",
   "rationale": "<one sentence>"}
]}

Only output JSON. No markdown fences, no explanation outside the object.
"""


SECTION_PASS_SYSTEM = """You are a careful writing coach helping a researcher
review a single section of a longer work. The section's draft and pinned
evidence are provided. Stay grounded: do not invent facts. Cite pinned
evidence by its [@srcN] key when relevant.
"""


@dataclass
class Verdict:
    pair: tuple[int, int]
    verdict: str
    rationale: str


def _truncate(text: str, n: int = 1500) -> str:
    text = text.strip()
    return text if len(text) <= n else text[: n - 1] + "…"


async def generate_style_profile(samples: list[str], *, mode: Mode = "default") -> str:
    """Run the style-distillation prompt; return Markdown profile."""
    from app.services.model_gateway import get_gateway

    gw = get_gateway()
    bullets = "\n\n".join(f"### Sample {i + 1}\n\n{_truncate(s, 4000)}" for i, s in enumerate(samples))
    return await gw.complete(
        system=STYLE_PROFILE_SYSTEM,
        messages=[{"role": "user", "content": bullets}],
        mode=mode,
        max_tokens=900,
        temperature=0.3,
    )


def style_profile_for_prompt(profile_md: str) -> str:
    """Wrap a stored profile so it can be appended to a system prompt."""
    profile_md = profile_md.strip()
    if not profile_md:
        return ""
    return (
        "\n\nWhen drafting prose for the user, mimic the following voice "
        "without copying its content. Treat it as advisory; never let it "
        "override grounding requirements.\n\n--- VOICE PROFILE ---\n"
        f"{profile_md}\n--- END VOICE PROFILE ---\n"
    )


async def detect_contradictions(
    quotes: list[tuple[int, str, str]],
    *,
    mode: Mode = "default",
) -> list[Verdict]:
    """quotes: list of (id, source_title, text). Returns pairwise verdicts."""
    if len(quotes) < 2:
        return []
    from app.services.model_gateway import get_gateway

    gw = get_gateway()
    payload = "\n\n".join(
        f"id={qid}  source={src!r}\n{_truncate(text, 1200)}" for qid, src, text in quotes
    )
    raw = await gw.complete(
        system=CONTRADICTION_SYSTEM,
        messages=[{"role": "user", "content": payload}],
        mode=mode,
        max_tokens=1500,
        temperature=0.1,
    )
    return _parse_verdicts(raw)


def _parse_verdicts(raw: str) -> list[Verdict]:
    raw = raw.strip()
    # Be tolerant of accidental fences.
    fence = re.match(r"^```(?:json)?\s*(.*?)```\s*$", raw, flags=re.DOTALL)
    if fence:
        raw = fence.group(1).strip()
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("contradiction model returned non-JSON: %s", raw[:200])
        return []
    out: list[Verdict] = []
    for v in obj.get("verdicts", []):
        try:
            a, b = v["pair"]
            out.append(
                Verdict(
                    pair=(int(a), int(b)),
                    verdict=str(v.get("verdict", "unclear")).lower(),
                    rationale=str(v.get("rationale", ""))[:500],
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return out


async def steel_man_section(
    *,
    section_title: str,
    draft_text: str,
    evidence_blob: str,
    mode: Mode = "default",
) -> str:
    """Steel-man pass: argue the strongest case the section is making."""
    from app.services.model_gateway import get_gateway

    gw = get_gateway()
    user = (
        f"Section: {section_title}\n\n"
        f"--- DRAFT ---\n{_truncate(draft_text, 6000)}\n--- END DRAFT ---\n\n"
        f"--- PINNED EVIDENCE ---\n{_truncate(evidence_blob, 8000)}\n--- END EVIDENCE ---\n\n"
        "Task: produce the strongest possible version of the argument this "
        "section is trying to make. Use only what is supported by the pinned "
        "evidence (cite by [@srcN] keys). Keep it under 400 words. Use plain "
        "prose, not bullets unless the source uses them."
    )
    return await gw.complete(
        system=SECTION_PASS_SYSTEM,
        messages=[{"role": "user", "content": user}],
        mode=mode,
        max_tokens=1200,
        temperature=0.4,
    )


async def whats_missing_section(
    *,
    section_title: str,
    draft_text: str,
    evidence_blob: str,
    mode: Mode = "default",
) -> str:
    """What's-missing pass: identify gaps in the argument."""
    from app.services.model_gateway import get_gateway

    gw = get_gateway()
    user = (
        f"Section: {section_title}\n\n"
        f"--- DRAFT ---\n{_truncate(draft_text, 6000)}\n--- END DRAFT ---\n\n"
        f"--- PINNED EVIDENCE ---\n{_truncate(evidence_blob, 8000)}\n--- END EVIDENCE ---\n\n"
        "Task: identify what is missing. Cover (in this order, but skip any "
        "that don't apply): unsupported claims that need a citation; obvious "
        "counter-arguments not addressed; relevant evidence types likely to "
        "exist but not cited; logical gaps or non-sequiturs; weasel words or "
        "vague quantifiers. Be concrete. Quote the offending phrase verbatim "
        "when possible. Bullet list, ≤8 items, each ≤2 sentences."
    )
    return await gw.complete(
        system=SECTION_PASS_SYSTEM,
        messages=[{"role": "user", "content": user}],
        mode=mode,
        max_tokens=1200,
        temperature=0.3,
    )
