"""
Automated Controlled Mock Tests for LLMRouter.
Validates:
1. Primary key receives HTTP 429 -> Second key succeeds.
2. All keys for one provider fail -> Automatic switching to next free provider.
3. Invalid key handling (HTTP 401/403) disables that key.
4. Free-Only Cost Protection blocks paid models (₹0 ongoing cost guarantee).
5. All providers exhausted raises AllProvidersExhaustedError cleanly.
"""

import pytest
from typing import Dict, List, Optional, Any, AsyncIterator
from jarvis.brain.router import LLMRouter, CostProtectionError, AllProvidersExhaustedError
from jarvis.brain.key_manager import KeyManager
from jarvis.brain.adapters.base import (
    BaseProviderAdapter,
    LLMResponse,
    RateLimitError,
    AuthError,
    QuotaExhaustedError,
)
from config.settings import Settings


class MockAdapter(BaseProviderAdapter):
    """Configurable mock adapter for controlled unit tests."""

    def __init__(self, name: str, default_model: str = "free-model", allowed_free: Optional[List[str]] = None):
        super().__init__(name, "https://mock.api", default_model, allowed_free or [default_model, "approved-free"])
        self.call_history: List[Dict[str, Any]] = []
        # Key -> list of exceptions or responses to produce
        self.responses_by_key: Dict[str, List[Any]] = {}

    def queue_response(self, key: str, outcome: Any):
        if key not in self.responses_by_key:
            self.responses_by_key[key] = []
        self.responses_by_key[key].append(outcome)

    async def generate(
        self,
        messages: List[Dict[str, str]],
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        self.call_history.append({"key": api_key, "model": model or self.default_model})
        key_str = api_key or "local"
        queue = self.responses_by_key.get(key_str, [])

        if queue:
            outcome = queue.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        return LLMResponse(
            content=f"Hello from {self.name}",
            model=model or self.default_model,
            provider=self.name,
            key_masked="mock-key",
        )

    async def stream(
        self,
        messages: List[Dict[str, str]],
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]:
        yield f"Hello from {self.name}"


def create_isolated_settings(provider_keys: Dict[str, List[str]], priority: Optional[List[str]] = None) -> Settings:
    """Helper to create fresh, isolated settings per test case."""
    s = Settings()
    s.free_only_mode = True
    s.provider_priority = priority or ["openrouter", "groq", "gemini", "ollama", "sarvam"]
    s.api_keys = provider_keys
    return s


@pytest.mark.asyncio
async def test_scenario_1_primary_key_429_second_key_succeeds():
    """
    Scenario: Primary key receives HTTP 429.
    Expected: Key 1 is put on cooldown, Key 2 is automatically tried and succeeds.
    """
    settings = create_isolated_settings({"openrouter": ["or_key_1", "or_key_2"]})
    km = KeyManager(default_cooldown_seconds=10.0)

    mock_openrouter = MockAdapter("openrouter", default_model="openai/gpt-oss-20b:free")
    mock_openrouter.queue_response("or_key_1", RateLimitError("Rate limit exceeded 429", retry_after=5.0))
    mock_openrouter.queue_response(
        "or_key_2",
        LLMResponse(content="At your service, sir.", model="openai/gpt-oss-20b:free", provider="openrouter", key_masked="or_ke...ey_2")
    )

    adapters = {"openrouter": mock_openrouter}
    router = LLMRouter(custom_settings=settings, key_manager=km, adapters=adapters)

    resp = await router.generate([{"role": "user", "content": "Hello Jarvis"}])

    assert resp.content == "At your service, sir."
    assert resp.provider == "openrouter"
    calls = [c["key"] for c in mock_openrouter.call_history]
    assert calls == ["or_key_1", "or_key_2"]
    # Key 1 must now be in cooldown
    info_1 = km._find_key_info("openrouter", "or_key_1")
    assert info_1.status.value == "COOLDOWN"


@pytest.mark.asyncio
async def test_scenario_2_all_keys_fail_failover_to_next_free_provider():
    """
    Scenario: All keys for OpenRouter fail.
    Expected: Router fails over seamlessly to Groq (next free provider in priority list).
    """
    settings = create_isolated_settings({
        "openrouter": ["or_key_1"],
        "groq": ["groq_key_1"],
    })
    km = KeyManager(default_cooldown_seconds=10.0)

    mock_openrouter = MockAdapter("openrouter")
    mock_openrouter.queue_response("or_key_1", QuotaExhaustedError("OpenRouter monthly credits depleted"))

    mock_groq = MockAdapter("groq", default_model="llama-3.3-70b-versatile")
    mock_groq.queue_response(
        "groq_key_1",
        LLMResponse(content="Groq responding at high speed, sir.", model="llama-3.3-70b-versatile", provider="groq")
    )

    adapters = {"openrouter": mock_openrouter, "groq": mock_groq}
    router = LLMRouter(custom_settings=settings, key_manager=km, adapters=adapters)

    resp = await router.generate([{"role": "user", "content": "Status report"}])

    assert resp.provider == "groq"
    assert resp.content == "Groq responding at high speed, sir."
    assert mock_openrouter.call_history == [{"key": "or_key_1", "model": "free-model"}]
    assert mock_groq.call_history == [{"key": "groq_key_1", "model": "llama-3.3-70b-versatile"}]


@pytest.mark.asyncio
async def test_scenario_3_invalid_key_handling():
    """
    Scenario: Key receives HTTP 401/403 Invalid API Key.
    Expected: Key is permanently marked INVALID and disabled. Second key is used.
    """
    settings = create_isolated_settings({"openrouter": ["invalid_key", "good_key"]})
    km = KeyManager()

    mock_openrouter = MockAdapter("openrouter")
    mock_openrouter.queue_response("invalid_key", AuthError("Unauthorized: Key is invalid"))
    mock_openrouter.queue_response("good_key", LLMResponse(content="Ready, sir.", model="free-model", provider="openrouter"))

    adapters = {"openrouter": mock_openrouter}
    router = LLMRouter(custom_settings=settings, key_manager=km, adapters=adapters)

    resp = await router.generate([{"role": "user", "content": "Ping"}])

    assert resp.content == "Ready, sir."
    bad_info = km._find_key_info("openrouter", "invalid_key")
    assert bad_info.status.value == "INVALID"
    # Calling get_available_key should only yield good_key
    assert km.get_available_key("openrouter").key == "good_key"


@pytest.mark.asyncio
async def test_scenario_4_free_only_cost_protection():
    """
    Scenario: User or system requests a paid model when free_only_mode is active.
    Expected: CostProtectionError prevents calling the paid model (target ₹0 ongoing cost).
    """
    settings = create_isolated_settings({"openrouter": ["or_key_1"]})
    settings.free_only_mode = True
    km = KeyManager()

    mock_openrouter = MockAdapter("openrouter", default_model="openai/gpt-oss-20b:free", allowed_free=["openai/gpt-oss-20b:free"])
    adapters = {"openrouter": mock_openrouter}
    router = LLMRouter(custom_settings=settings, key_manager=km, adapters=adapters)

    # Attempting to call an expensive paid model like "openai/gpt-4o"
    with pytest.raises(AllProvidersExhaustedError):
        await router.generate([{"role": "user", "content": "Test"}], model="openai/gpt-4o")

    # Verify that mock_openrouter was NEVER called with the paid model
    assert len(mock_openrouter.call_history) == 0


@pytest.mark.asyncio
async def test_scenario_5_all_providers_exhausted():
    """
    Scenario: All keys across all configured providers fail.
    Expected: Clean AllProvidersExhaustedError without crashing the process.
    """
    settings = create_isolated_settings({
        "openrouter": ["or_1"],
        "groq": ["groq_1"],
    }, priority=["openrouter", "groq"])
    km = KeyManager()

    mock_openrouter = MockAdapter("openrouter")
    mock_openrouter.queue_response("or_1", QuotaExhaustedError("No balance"))

    mock_groq = MockAdapter("groq")
    mock_groq.queue_response("groq_1", QuotaExhaustedError("No balance"))

    adapters = {"openrouter": mock_openrouter, "groq": mock_groq}
    router = LLMRouter(custom_settings=settings, key_manager=km, adapters=adapters)

    with pytest.raises(AllProvidersExhaustedError) as exc_info:
        await router.generate([{"role": "user", "content": "Hello"}])

    assert "All configured free providers" in str(exc_info.value)
