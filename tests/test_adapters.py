"""
Tests for adapter free-model eligibility and error parsing logic.
"""

from jarvis.brain.adapters.openrouter import OpenRouterAdapter
from jarvis.brain.adapters.groq import GroqAdapter
from jarvis.brain.adapters.gemini import GeminiAdapter
from jarvis.brain.adapters.ollama import OllamaAdapter
from jarvis.brain.adapters.sarvam import SarvamAdapter


def test_openrouter_free_model_eligibility():
    adapter = OpenRouterAdapter()
    assert adapter.default_model == "openrouter/free"
    assert adapter.is_free_eligible("openrouter/free") is True
    assert adapter.is_free_eligible("openai/gpt-oss-20b:free") is True
    assert adapter.is_free_eligible("meta-llama/llama-3.3-70b-instruct:free") is True
    assert adapter.is_free_eligible("deepseek/deepseek-r1:free") is True
    assert adapter.is_free_eligible("custom/model:free") is True
    assert adapter.is_free_eligible("openai/gpt-4o") is False
    assert adapter.is_free_eligible("anthropic/claude-3.5-sonnet") is False


def test_groq_free_model_eligibility():
    adapter = GroqAdapter()
    assert adapter.default_model == "openai/gpt-oss-120b"
    assert adapter.is_free_eligible("llama-3.3-70b-versatile") is True
    assert adapter.is_free_eligible("llama-3.1-8b-instant") is True
    assert adapter.is_free_eligible("openai/gpt-oss-120b") is True
    assert adapter.is_free_eligible("openai/gpt-oss-20b") is True
    assert adapter.is_free_eligible("qwen/qwen3.8-27b") is True
    assert adapter.is_free_eligible("paid/enterprise-model") is False


def test_gemini_free_model_eligibility():
    adapter = GeminiAdapter()
    assert adapter.default_model == "gemini-2.0-flash"
    assert adapter.is_free_eligible("gemini-2.0-flash") is True
    assert adapter.is_free_eligible("gemini-1.5-flash") is True
    assert adapter.is_free_eligible("gemini-1.5-flash-8b") is True
    assert adapter.is_free_eligible("gemini-1.5-pro") is False


def test_ollama_all_models_free():
    adapter = OllamaAdapter()
    assert adapter.default_model == "llama3"
    assert adapter.is_free_eligible("llama3") is True
    assert adapter.is_free_eligible("any-custom-local-model") is True


def test_sarvam_free_model_eligibility():
    adapter = SarvamAdapter()
    assert adapter.default_model == "sarvam-105b-conversations"
    assert adapter.is_free_eligible("sarvam-105b-conversations") is True
    assert adapter.is_free_eligible("sarvam-105b") is True
    assert adapter.is_free_eligible("sarvam-2b") is True
    assert adapter.is_free_eligible("unknown-paid-model") is False


def test_settings_env_default_model_overrides_and_fallback(monkeypatch):
    from config.settings import Settings

    # Test GEMINI_DEFAULT_MODEL override
    monkeypatch.setenv("GEMINI_DEFAULT_MODEL", "gemini-2.0-flash-exp")
    s = Settings()
    assert s.providers_config["gemini"]["default_model"] == "gemini-2.0-flash-exp"

    # Test fallback if user had GEMINI_LDEFAULT_MODE
    monkeypatch.delenv("GEMINI_DEFAULT_MODEL", raising=False)
    monkeypatch.setenv("GEMINI_LDEFAULT_MODE", "gemini-1.5-flash-8b")
    s2 = Settings()
    assert s2.providers_config["gemini"]["default_model"] == "gemini-1.5-flash-8b"

