"""Thin wrapper around Anthropic's SDK.

All Claude calls in the app go through this so we have one place to:
- swap models (default vs hard-synthesis),
- meter / log / cache later (Phase 4),
- substitute a local LLM in privacy mode later.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Literal

from anthropic import AsyncAnthropic

from app.config import get_settings

logger = logging.getLogger(__name__)


Mode = Literal["default", "hard"]


class ModelGateway:
    def __init__(self) -> None:
        s = get_settings()
        self._client = AsyncAnthropic(api_key=s.anthropic_api_key)
        self._default_model = s.anthropic_model_default
        self._hard_model = s.anthropic_model_hard

    def model_for(self, mode: Mode) -> str:
        return self._hard_model if mode == "hard" else self._default_model

    async def stream_chat(
        self,
        *,
        system: str,
        messages: list[dict],
        mode: Mode = "default",
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> AsyncIterator[str]:
        """Yield text deltas from the model. Caller should accumulate."""
        model = self.model_for(mode)
        async with self._client.messages.stream(
            model=model,
            system=system,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        ) as stream:
            async for delta in stream.text_stream:
                yield delta

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


_gateway: ModelGateway | None = None


def get_gateway() -> ModelGateway:
    global _gateway
    if _gateway is None:
        _gateway = ModelGateway()
    return _gateway
