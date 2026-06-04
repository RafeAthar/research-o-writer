"""Thin wrapper around Anthropic's SDK.

All Claude calls in the app go through this so we have one place to:
- swap models (default vs hard-synthesis),
- meter / log / cache later (Phase 4),
- substitute a local LLM in privacy mode later.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal

from anthropic import AsyncAnthropic

from app.config import get_settings

logger = logging.getLogger(__name__)


Mode = Literal["default", "hard"]


@dataclass(slots=True)
class StreamEvent:
    """One event from a streaming model call.

    kind="delta" -> incremental text in .text
    kind="done"  -> end of stream; .stop_reason is set (e.g. "end_turn",
                    "max_tokens", "stop_sequence")
    """

    kind: Literal["delta", "done"]
    text: str = ""
    stop_reason: str | None = None


class ModelGateway:
    def __init__(self) -> None:
        s = get_settings()
        self._client = AsyncAnthropic(api_key=s.anthropic_api_key)
        self._default_model = s.anthropic_model_default
        self._hard_model = s.anthropic_model_hard
        self._fast_model = s.anthropic_model_fast

    def model_for(self, mode: Mode) -> str:
        return self._hard_model if mode == "hard" else self._default_model

    @property
    def fast_model(self) -> str:
        return self._fast_model

    async def stream_chat(
        self,
        *,
        system: str,
        messages: list[dict],
        mode: Mode = "default",
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> AsyncIterator[StreamEvent]:
        """Yield StreamEvents from the model.

        Emits one or more ``kind="delta"`` events with incremental text, then
        a final ``kind="done"`` event carrying the Anthropic stop_reason so
        callers can detect ``max_tokens`` and offer a Continue affordance.
        """
        model = self.model_for(mode)
        async with self._client.messages.stream(
            model=model,
            system=system,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        ) as stream:
            async for delta in stream.text_stream:
                yield StreamEvent(kind="delta", text=delta)
            final = await stream.get_final_message()
            yield StreamEvent(kind="done", stop_reason=getattr(final, "stop_reason", None))

    async def complete(
        self,
        *,
        system: str,
        messages: list[dict],
        mode: Mode = "default",
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> str:
        model = self.model_for(mode)
        msg = await self._client.messages.create(
            model=model,
            system=system,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        # Concatenate text blocks (anthropic responses are content blocks).
        parts: list[str] = []
        for block in msg.content:
            if getattr(block, "type", "") == "text":
                parts.append(block.text)
        return "".join(parts)

    async def complete_fast(
        self,
        *,
        system: str,
        prompt: str,
        max_tokens: int = 64,
        temperature: float = 0.3,
    ) -> str:
        """One-shot Haiku call for ancillary work (titles, follow-ups).

        Returns the joined text content. Caller handles parsing/validation —
        we keep this dumb on purpose so it stays usable for multiple callers.
        """
        msg = await self._client.messages.create(
            model=self._fast_model,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        parts: list[str] = []
        for block in msg.content:
            if getattr(block, "type", "") == "text":
                parts.append(block.text)
        return "".join(parts).strip()


_gateway: ModelGateway | None = None
_gateway_lock = threading.Lock()


def get_gateway() -> ModelGateway:
    global _gateway
    if _gateway is None:
        with _gateway_lock:
            if _gateway is None:
                _gateway = ModelGateway()
    return _gateway
