"""Unit tests for the LLM factory module.

Tests cover:
- Provider selection via AGENTFORGE_LLM_PROVIDER env var
- Graceful None return for "none" / unset
- Unknown provider raises LLMError
- Client repr / provider_name properties
"""

from __future__ import annotations

import os
import pytest


class TestGetLlmClientNone:
    """When provider is none/unset, get_llm_client() must return None."""

    def test_default_returns_none(self, monkeypatch):
        monkeypatch.delenv("AGENTFORGE_LLM_PROVIDER", raising=False)
        from agentforge.llm.factory import get_llm_client
        assert get_llm_client() is None

    def test_explicit_none_returns_none(self, monkeypatch):
        monkeypatch.setenv("AGENTFORGE_LLM_PROVIDER", "none")
        from agentforge.llm.factory import get_llm_client
        assert get_llm_client() is None

    def test_disabled_returns_none(self, monkeypatch):
        monkeypatch.setenv("AGENTFORGE_LLM_PROVIDER", "disabled")
        from agentforge.llm.factory import get_llm_client
        assert get_llm_client() is None

    def test_off_returns_none(self, monkeypatch):
        monkeypatch.setenv("AGENTFORGE_LLM_PROVIDER", "off")
        from agentforge.llm.factory import get_llm_client
        assert get_llm_client() is None


class TestGetLlmClientUnknown:
    """Unknown provider names must raise LLMError."""

    def test_unknown_provider_raises(self, monkeypatch):
        from agentforge.llm.base import LLMError
        monkeypatch.setenv("AGENTFORGE_LLM_PROVIDER", "not_a_real_provider")
        from agentforge.llm.factory import get_llm_client
        with pytest.raises(LLMError, match="Unknown LLM provider"):
            get_llm_client()


class TestOllamaClient:
    """Ollama client can be instantiated without an API key (uses httpx)."""

    def test_ollama_instantiation(self, monkeypatch):
        monkeypatch.setenv("AGENTFORGE_LLM_PROVIDER", "ollama")
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
        monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
        from agentforge.llm.ollama_client import OllamaClient
        client = OllamaClient()
        assert "Ollama" in client.provider_name
        assert "qwen2.5-coder:7b" in client.provider_name

    def test_ollama_provider_name_contains_url(self, monkeypatch):
        from agentforge.llm.ollama_client import OllamaClient
        client = OllamaClient(base_url="http://myhost:11434", model="codellama:13b")
        assert "myhost" in client.provider_name
        assert "codellama:13b" in client.provider_name


class TestOpenAIClientMissingKey:
    """OpenAI client must raise LLMError when key is absent."""

    def test_missing_key_raises(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        # Guard: only run if openai is installed
        pytest.importorskip("openai")
        from agentforge.llm.base import LLMError
        from agentforge.llm.openai_client import OpenAIClient
        with pytest.raises(LLMError, match="OPENAI_API_KEY"):
            OpenAIClient(api_key=None)


class TestAnthropicClientMissingKey:
    """Anthropic client must raise LLMError when key is absent."""

    def test_missing_key_raises(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        pytest.importorskip("anthropic")
        from agentforge.llm.base import LLMError
        from agentforge.llm.anthropic_client import AnthropicClient
        with pytest.raises(LLMError, match="ANTHROPIC_API_KEY"):
            AnthropicClient(api_key=None)


class TestGeminiClientMissingKey:
    """Gemini client must raise LLMError when key is absent."""

    def test_missing_key_raises(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        pytest.importorskip("google.generativeai")
        from agentforge.llm.base import LLMError
        from agentforge.llm.gemini_client import GeminiClient
        with pytest.raises(LLMError, match="GEMINI_API_KEY"):
            GeminiClient(api_key=None)
