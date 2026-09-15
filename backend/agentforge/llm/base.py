"""Abstract LLM client interface for AgentForge.

All provider implementations must subclass LLMClient and implement:
    - complete()            → plain text generation
    - complete_with_json()  → structured JSON output validated by a Pydantic model

The caller never interacts with provider SDKs directly; only this interface.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class ChatMessage(BaseModel):
    """A single message in a conversation."""

    role: str  # "system" | "user" | "assistant"
    content: str


class LLMError(Exception):
    """Raised when an LLM call fails in a non-recoverable way."""


class LLMClient(ABC):
    """Unified interface for LLM text completion backends."""

    # ------------------------------------------------------------------
    # Abstract interface — providers must implement these two methods
    # ------------------------------------------------------------------

    @abstractmethod
    async def complete(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.2,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> str:
        """Generate a text completion from a sequence of chat messages.

        Args:
            messages:    Ordered list of ChatMessage objects (system + user + history).
            temperature: Sampling temperature; lower = more deterministic.
            max_tokens:  Upper bound on generated tokens.
            **kwargs:    Provider-specific overrides.

        Returns:
            The assistant's text response as a plain string.

        Raises:
            LLMError: If the provider returns an unrecoverable error.
        """

    # ------------------------------------------------------------------
    # Derived helpers — implementations may override for native JSON mode
    # ------------------------------------------------------------------

    async def complete_with_json(
        self,
        messages: list[ChatMessage],
        schema: Type[T],
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> T:
        """Generate a structured JSON completion validated against a Pydantic model.

        The base implementation appends a schema-awareness instruction to the last
        user message and parses the raw text response. Providers that support native
        JSON/tool modes may override this method for better reliability.

        Args:
            messages:    Chat history.
            schema:      Pydantic model class the response must conform to.
            temperature: Lower temperatures yield more reliable JSON.
            max_tokens:  Token budget.

        Returns:
            An instance of ``schema`` populated from the LLM's JSON output.

        Raises:
            LLMError: If the response cannot be parsed or validated.
        """
        # Append JSON-format instruction to the conversation
        augmented = list(messages)
        schema_hint = schema.model_json_schema()
        json_instruction = ChatMessage(
            role="user",
            content=(
                f"\n\nRespond ONLY with a valid JSON object conforming to this schema "
                f"(no markdown fences, no prose, no trailing commas):\n"
                f"{json.dumps(schema_hint, indent=2)}"
            ),
        )
        augmented.append(json_instruction)

        raw = await self.complete(augmented, temperature=temperature, max_tokens=max_tokens, **kwargs)

        # Strip markdown code fences if the model wrapped the JSON
        cleaned = _strip_code_fences(raw)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise LLMError(f"LLM returned invalid JSON: {exc}\nRaw response:\n{cleaned[:500]}") from exc

        try:
            return schema.model_validate(data)
        except ValidationError as exc:
            raise LLMError(f"LLM JSON failed Pydantic validation: {exc}\nData: {data}") from exc

    # ------------------------------------------------------------------
    # Provider metadata
    # ------------------------------------------------------------------

    @property
    def provider_name(self) -> str:
        """Human-readable provider identifier."""
        return type(self).__name__

    def __repr__(self) -> str:
        return f"<{self.provider_name}>"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences from an LLM response string."""
    text = text.strip()
    for fence_lang in ("```json", "```JSON", "```"):
        if text.startswith(fence_lang):
            text = text[len(fence_lang):]
            break
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()
