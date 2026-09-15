"""LLM provider factory for AgentForge.

Reads AGENTFORGE_LLM_PROVIDER environment variable to select which backend to use.

Supported values:
    openai      → OpenAI / Azure OpenAI (requires OPENAI_API_KEY)
    anthropic   → Anthropic Claude    (requires ANTHROPIC_API_KEY)
    gemini      → Google Gemini       (requires GEMINI_API_KEY)
    ollama      → Local Ollama        (no API key; requires running `ollama serve`)
    none        → Disabled; agents fall back to deterministic heuristics

Default: "none" (safe — no external calls, existing behaviour preserved)
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from agentforge.llm.base import LLMClient, LLMError

logger = logging.getLogger(__name__)

_PROVIDER_ENV = "AGENTFORGE_LLM_PROVIDER"


def get_llm_client() -> Optional[LLMClient]:
    """Instantiate and return the configured LLM client, or None if disabled.

    The provider is controlled entirely by environment variables so no code
    changes are required when switching backends.

    Returns:
        An LLMClient instance ready for use, or None if
        AGENTFORGE_LLM_PROVIDER is "none" or unset.

    Raises:
        LLMError: If the configured provider is unknown or cannot be
            initialised (e.g. missing API key or SDK not installed).
    """
    provider = os.environ.get(_PROVIDER_ENV, "none").strip().lower()

    if provider in ("none", "", "disabled", "off"):
        logger.info(
            "LLM provider is disabled (%s=%s). "
            "Agents will use deterministic heuristics.",
            _PROVIDER_ENV,
            provider,
        )
        return None

    logger.info("Initialising LLM provider: %s", provider)

    if provider == "openai":
        from agentforge.llm.openai_client import OpenAIClient
        client = OpenAIClient()

    elif provider == "anthropic":
        from agentforge.llm.anthropic_client import AnthropicClient
        client = AnthropicClient()

    elif provider == "gemini":
        from agentforge.llm.gemini_client import GeminiClient
        client = GeminiClient()

    elif provider == "ollama":
        from agentforge.llm.ollama_client import OllamaClient
        client = OllamaClient()

    else:
        raise LLMError(
            f"Unknown LLM provider '{provider}'. "
            f"Set {_PROVIDER_ENV} to one of: openai, anthropic, gemini, ollama, none"
        )

    logger.info("LLM client ready: %r", client)
    return client
