"""Ollama LLM client for AgentForge (local, no API key required).

Ollama runs models locally via a REST API. See https://ollama.com/

Environment variables:
    OLLAMA_BASE_URL    Optional. Defaults to "http://localhost:11434".
    OLLAMA_MODEL       Optional. Defaults to "qwen2.5-coder:7b".

Recommended coding models to pull:
    ollama pull qwen2.5-coder:7b      # fast, 7B params
    ollama pull deepseek-coder:6.7b   # strong code model
    ollama pull codellama:13b         # Meta's Code Llama
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

from agentforge.llm.base import ChatMessage, LLMClient, LLMError

logger = logging.getLogger(__name__)


class OllamaClient(LLMClient):
    """LLM client backed by a locally running Ollama instance.

    Uses httpx (already a core AgentForge dependency) to call the Ollama
    /api/chat endpoint — no additional SDK installation needed.
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 180.0,
    ) -> None:
        self._base_url = (base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self._model = model or os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:7b")
        self._timeout = timeout

    @property
    def provider_name(self) -> str:
        return f"Ollama({self._model}@{self._base_url})"

    async def complete(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.2,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> str:
        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        url = f"{self._base_url}/api/chat"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("message", {}).get("content", "")
        except httpx.ConnectError as exc:
            raise LLMError(
                f"Cannot connect to Ollama at {self._base_url}. "
                "Is Ollama running? Start it with `ollama serve`."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise LLMError(f"Ollama HTTP error {exc.response.status_code}: {exc.response.text}") from exc
        except Exception as exc:
            raise LLMError(f"Ollama request failed: {exc}") from exc

    async def is_model_available(self) -> bool:
        """Check whether the configured model is available in the local Ollama instance."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self._base_url}/api/tags")
                resp.raise_for_status()
                models = resp.json().get("models", [])
                return any(m.get("name", "").startswith(self._model.split(":")[0]) for m in models)
        except Exception:
            return False
