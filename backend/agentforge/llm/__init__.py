"""agentforge.llm — Pluggable LLM provider layer for AgentForge.

Quick start:
    Set AGENTFORGE_LLM_PROVIDER to one of: openai, anthropic, gemini, ollama, none
    Set the corresponding API key environment variable (see each client module).

    from agentforge.llm import get_llm_client
    client = get_llm_client()   # None if provider == "none"
"""

from agentforge.llm.base import ChatMessage, LLMClient, LLMError
from agentforge.llm.factory import get_llm_client

__all__ = [
    "ChatMessage",
    "LLMClient",
    "LLMError",
    "get_llm_client",
]
