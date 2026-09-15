"""Google Gemini LLM client for AgentForge.

Environment variables:
    GEMINI_API_KEY    Required. Your Google AI Studio API key.
    GEMINI_MODEL      Optional. Defaults to "gemini-2.0-flash".
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


class GeminiClient(LLMClient):
    """LLM client backed by the Google Generative AI (Gemini) API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        try:
            import google.generativeai as genai  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "google-generativeai package is required for the Gemini provider. "
                "Install it with: pip install 'agentforge[llm-gemini]'"
            ) from exc

        self._genai = genai
        self._model_name = model or os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
        resolved_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not resolved_key:
            raise LLMError(
                "GEMINI_API_KEY environment variable is not set. "
                "Set it or use AGENTFORGE_LLM_PROVIDER=none to disable LLM."
            )
        genai.configure(api_key=resolved_key)

    @property
    def provider_name(self) -> str:
        return f"Gemini({self._model_name})"

    def _build_gemini_contents(self, messages: list[ChatMessage]) -> tuple[str | None, list[dict]]:
        """Convert ChatMessage list to Gemini's (system_instruction, contents) format."""
        system_parts = [m.content for m in messages if m.role == "system"]
        system_instruction = "\n\n".join(system_parts) if system_parts else None

        contents = []
        for m in messages:
            if m.role == "system":
                continue
            # Gemini uses "user" / "model" roles
            gemini_role = "model" if m.role == "assistant" else "user"
            contents.append({"role": gemini_role, "parts": [{"text": m.content}]})

        return system_instruction, contents

    async def complete(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.2,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> str:
        import asyncio

        system_instruction, contents = self._build_gemini_contents(messages)

        model_kwargs: dict[str, Any] = {"model_name": self._model_name}
        if system_instruction:
            model_kwargs["system_instruction"] = system_instruction

        generation_config = self._genai.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        try:
            model = self._genai.GenerativeModel(**model_kwargs)
            # google-generativeai has async support via generate_content_async
            response = await model.generate_content_async(
                contents,
                generation_config=generation_config,
            )
            return response.text or ""
        except Exception as exc:
            raise LLMError(f"Gemini API error: {exc}") from exc

    async def complete_with_json(
        self,
        messages: list[ChatMessage],
        schema: Type[T],
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> T:
        """Uses Gemini's JSON response MIME type for reliable structured output."""
        from pydantic import ValidationError

        system_instruction, contents = self._build_gemini_contents(messages)

        schema_hint = schema.model_json_schema()
        # Append schema instruction to last user message
        if contents:
            last = contents[-1]
            extra_text = (
                f"\n\nRespond ONLY with a valid JSON object matching this schema "
                f"(no markdown, no prose):\n{json.dumps(schema_hint, indent=2)}"
            )
            last["parts"][-1]["text"] += extra_text
        else:
            contents.append({"role": "user", "parts": [{"text": json.dumps(schema_hint)}]})

        model_kwargs: dict[str, Any] = {"model_name": self._model_name}
        if system_instruction:
            model_kwargs["system_instruction"] = system_instruction

        generation_config = self._genai.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            response_mime_type="application/json",
        )

        try:
            model = self._genai.GenerativeModel(**model_kwargs)
            response = await model.generate_content_async(
                contents,
                generation_config=generation_config,
            )
            raw = response.text or ""
        except Exception as exc:
            raise LLMError(f"Gemini API error: {exc}") from exc

        cleaned = _strip_code_fences(raw)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise LLMError(f"Gemini returned invalid JSON: {exc}\nRaw: {cleaned[:500]}") from exc

        try:
            return schema.model_validate(data)
        except ValidationError as exc:
            raise LLMError(f"Gemini JSON failed Pydantic validation: {exc}") from exc
