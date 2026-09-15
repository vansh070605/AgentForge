"""Anthropic Claude LLM client for AgentForge.

Environment variables:
    ANTHROPIC_API_KEY    Required. Your Anthropic API key.
    ANTHROPIC_MODEL      Optional. Defaults to "claude-3-5-sonnet-20241022".
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Type, TypeVar

from pydantic import BaseModel

from agentforge.llm.base import ChatMessage, LLMClient, LLMError, _strip_code_fences

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class AnthropicClient(LLMClient):
    """LLM client backed by the Anthropic Messages API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        try:
            import anthropic as _anthropic  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "anthropic package is required for the Anthropic provider. "
                "Install it with: pip install 'agentforge[llm-anthropic]'"
            ) from exc

        self._anthropic = _anthropic
        self._model = model or os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not resolved_key:
            raise LLMError(
                "ANTHROPIC_API_KEY environment variable is not set. "
                "Set it or use AGENTFORGE_LLM_PROVIDER=none to disable LLM."
            )
        self._client = _anthropic.AsyncAnthropic(api_key=resolved_key)

    @property
    def provider_name(self) -> str:
        return f"Anthropic({self._model})"

    async def complete(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.2,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> str:
        # Anthropic separates the system prompt from the message list
        system_parts = [m.content for m in messages if m.role == "system"]
        system_text = "\n\n".join(system_parts) if system_parts else None
        conversation = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role != "system"
        ]

        try:
            create_kwargs: dict[str, Any] = {
                "model": self._model,
                "messages": conversation,
                "temperature": temperature,
                "max_tokens": max_tokens,
                **kwargs,
            }
            if system_text:
                create_kwargs["system"] = system_text

            response = await self._client.messages.create(**create_kwargs)
            return response.content[0].text if response.content else ""
        except Exception as exc:
            raise LLMError(f"Anthropic API error: {exc}") from exc
