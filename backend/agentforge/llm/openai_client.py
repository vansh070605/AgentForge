"""OpenAI / Azure OpenAI LLM client for AgentForge.

Environment variables:
    OPENAI_API_KEY       Required. Your OpenAI API key.
    OPENAI_MODEL         Optional. Defaults to "gpt-4o".
    OPENAI_BASE_URL      Optional. Override for Azure OpenAI or compatible proxies.
    OPENAI_API_VERSION   Optional. Required for Azure deployments.
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


class OpenAIClient(LLMClient):
    """LLM client backed by the OpenAI Chat Completions API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        try:
            from openai import AsyncOpenAI  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "openai package is required for the OpenAI provider. "
                "Install it with: pip install 'agentforge[llm-openai]'"
            ) from exc

        self._model = model or os.environ.get("OPENAI_MODEL", "gpt-4o")
        resolved_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not resolved_key:
            raise LLMError(
                "OPENAI_API_KEY environment variable is not set. "
                "Set it or use AGENTFORGE_LLM_PROVIDER=none to disable LLM."
            )

        client_kwargs: dict[str, Any] = {"api_key": resolved_key}
        resolved_url = base_url or os.environ.get("OPENAI_BASE_URL")
        if resolved_url:
            client_kwargs["base_url"] = resolved_url

        self._client = AsyncOpenAI(**client_kwargs)  # type: ignore[arg-type]

    @property
    def provider_name(self) -> str:
        return f"OpenAI({self._model})"

    async def complete(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.2,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> str:
        oai_messages = [{"role": m.role, "content": m.content} for m in messages]
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=oai_messages,  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            content = response.choices[0].message.content
            return content or ""
        except Exception as exc:
            raise LLMError(f"OpenAI API error: {exc}") from exc

    async def complete_with_json(
        self,
        messages: list[ChatMessage],
        schema: Type[T],
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> T:
        """Uses OpenAI's native JSON mode for more reliable structured output."""
        from pydantic import ValidationError

        oai_messages = [{"role": m.role, "content": m.content} for m in messages]
        schema_hint = schema.model_json_schema()
        oai_messages.append({
            "role": "user",
            "content": (
                f"\n\nRespond ONLY with a valid JSON object matching this schema "
                f"(no markdown, no prose):\n{json.dumps(schema_hint, indent=2)}"
            ),
        })

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=oai_messages,  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content or ""
        except Exception as exc:
            raise LLMError(f"OpenAI API error: {exc}") from exc

        cleaned = _strip_code_fences(raw)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise LLMError(f"OpenAI returned invalid JSON: {exc}\nRaw: {cleaned[:500]}") from exc

        try:
            return schema.model_validate(data)
        except ValidationError as exc:
            raise LLMError(f"OpenAI JSON failed Pydantic validation: {exc}") from exc
