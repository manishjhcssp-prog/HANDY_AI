"""
JARVIS AI - Intelligent Multi-Provider Router with Automatic Failover
Executes the free-first strategy with multi-key rotation per provider,
cooldown tracking, and seamless fallback across OpenRouter, Groq, Gemini, Ollama, and Sarvam.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, AsyncIterator
from config.settings import Settings, settings as default_settings
from .key_manager import KeyManager, KeyStatus, KeyInfo
from .adapters.base import (
    BaseProviderAdapter,
    LLMResponse,
    RateLimitError,
    QuotaExhaustedError,
    AuthError,
    ServerError,
    ProviderError,
)
from .adapters.openrouter import OpenRouterAdapter
from .adapters.groq import GroqAdapter
from .adapters.gemini import GeminiAdapter
from .adapters.ollama import OllamaAdapter
from .adapters.sarvam import SarvamAdapter

logger = logging.getLogger("JARVIS.Router")


class CostProtectionError(Exception):
    """Raised when an attempt is made to use a paid model while free-only mode is active."""
    pass


class AllProvidersExhaustedError(Exception):
    """Raised when all configured providers and keys have failed or exhausted their quotas."""
    pass


class LLMRouter:
    def __init__(
        self,
        custom_settings: Optional[Settings] = None,
        key_manager: Optional[KeyManager] = None,
        adapters: Optional[Dict[str, BaseProviderAdapter]] = None,
    ):
        self.settings = custom_settings or default_settings
        self.key_manager = key_manager or KeyManager(
            default_cooldown_seconds=self.settings.router_settings.get("default_cooldown_seconds", 60.0)
        )

        # Register keys from configuration into key manager
        for provider, keys in self.settings.api_keys.items():
            if keys:
                self.key_manager.register_keys(provider, keys)

        # Initialize adapters
        self.adapters: Dict[str, BaseProviderAdapter] = adapters or {
            "openrouter": OpenRouterAdapter(
                base_url=self.settings.providers_config.get("openrouter", {}).get("base_url", "https://openrouter.ai/api/v1"),
                default_model=self.settings.providers_config.get("openrouter", {}).get("default_model", "openrouter/free"),
                allowed_free_models=self.settings.providers_config.get("openrouter", {}).get("allowed_free_models"),
            ),
            "groq": GroqAdapter(
                base_url=self.settings.providers_config.get("groq", {}).get("base_url", "https://api.groq.com/openai/v1"),
                default_model=self.settings.providers_config.get("groq", {}).get("default_model", "openai/gpt-oss-120b"),
                allowed_free_models=self.settings.providers_config.get("groq", {}).get("allowed_free_models"),
            ),
            "gemini": GeminiAdapter(
                base_url=self.settings.providers_config.get("gemini", {}).get("base_url", "https://generativelanguage.googleapis.com/v1beta"),
                default_model=self.settings.providers_config.get("gemini", {}).get("default_model", "gemini-2.0-flash"),
                allowed_free_models=self.settings.providers_config.get("gemini", {}).get("allowed_free_models"),
            ),
            "ollama": OllamaAdapter(
                base_url=self.settings.providers_config.get("ollama", {}).get("base_url", "http://localhost:11434"),
                default_model=self.settings.providers_config.get("ollama", {}).get("default_model", "llama3"),
                allowed_free_models=self.settings.providers_config.get("ollama", {}).get("allowed_free_models"),
            ),
            "sarvam": SarvamAdapter(
                base_url=self.settings.providers_config.get("sarvam", {}).get("base_url", "https://api.sarvam.ai"),
                default_model=self.settings.providers_config.get("sarvam", {}).get("default_model", "sarvam-105b-conversations"),
                allowed_free_models=self.settings.providers_config.get("sarvam", {}).get("allowed_free_models"),
            ),
        }

        # Telemetry
        self.active_provider: Optional[str] = None
        self.active_model: Optional[str] = None
        self.active_key_masked: str = "none"

    def get_provider_priority(self) -> List[str]:
        return list(self.settings.provider_priority)

    def _verify_free_only(self, provider: str, model: Optional[str]) -> None:
        """Enforces ₹0 ongoing API cost rule."""
        if not self.settings.free_only_mode:
            return

        adapter = self.adapters.get(provider)
        if not adapter:
            return

        target_model = model or adapter.default_model
        if not adapter.is_free_eligible(target_model):
            raise CostProtectionError(
                f"[Cost Protection] Model '{target_model}' on provider '{provider}' is not an approved free-tier model. "
                "Target is ₹0 ongoing API cost. Paid models require explicit approval."
            )

    async def generate(
        self,
        messages: List[Dict[str, str]],
        preferred_provider: Optional[str] = None,
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """
        Main entry point for generating completions with automatic multi-key rotation
        and seamless provider failover.
        """
        priority_list = self.get_provider_priority()
        if preferred_provider and preferred_provider in priority_list:
            # Move preferred provider to front
            priority_list.remove(preferred_provider)
            priority_list.insert(0, preferred_provider)

        attempted_providers = []

        for provider in priority_list:
            adapter = self.adapters.get(provider)
            if not adapter:
                continue

            # Free-only protection check
            try:
                self._verify_free_only(provider, model)
            except CostProtectionError as e:
                logger.warning(str(e))
                continue

            # Ollama does not require API keys
            is_local = (provider == "ollama")

            # Try available keys for this provider
            while True:
                key_info: Optional[KeyInfo] = None
                raw_key: Optional[str] = None

                if not is_local:
                    key_info = self.key_manager.get_available_key(provider)
                    if not key_info:
                        # No available keys for this provider right now
                        break
                    raw_key = key_info.key
                else:
                    raw_key = "local"

                masked = key_info.masked if key_info else "offline"
                self.active_provider = provider
                self.active_model = model or adapter.default_model
                self.active_key_masked = masked

                logger.info(
                    f"Routing request -> Provider: {provider} | Model: {self.active_model} | Key: {masked}"
                )

                try:
                    response = await adapter.generate(
                        messages=messages,
                        api_key=raw_key if not is_local else None,
                        model=model,
                        tools=tools,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    if key_info:
                        self.key_manager.mark_success(provider, raw_key)
                    return response

                except RateLimitError as e:
                    logger.warning(f"RateLimit on {provider} (Key: {masked}): {e.message}")
                    if key_info and raw_key:
                        self.key_manager.mark_rate_limited(provider, raw_key, retry_after=e.retry_after, reason=e.message)
                    # Loop and try next available key for same provider
                    continue

                except QuotaExhaustedError as e:
                    logger.warning(f"Quota Exhausted on {provider} (Key: {masked}): {e.message}")
                    if key_info and raw_key:
                        self.key_manager.mark_quota_exhausted(provider, raw_key, reason=e.message)
                    # Loop and try next available key for same provider
                    continue

                except AuthError as e:
                    logger.error(f"Auth Error on {provider} (Key: {masked}): {e.message}")
                    if key_info and raw_key:
                        self.key_manager.mark_invalid(provider, raw_key, reason=e.message)
                    # Loop and try next available key for same provider
                    continue

                except (ServerError, ProviderError) as e:
                    logger.warning(f"Transient error on {provider} (Key: {masked}): {e.message}")
                    # For local Ollama if not running, fail over immediately
                    if is_local:
                        break
                    # For cloud providers, retry bounded or rotate key
                    if key_info and raw_key:
                        self.key_manager.mark_rate_limited(provider, raw_key, retry_after=10.0, reason=e.message)
                    continue

                except Exception as e:
                    logger.error(f"Unexpected error executing {provider}: {str(e)}")
                    break

            attempted_providers.append(provider)
            logger.info(f"Provider '{provider}' exhausted or unavailable. Failing over to next priority provider.")

        raise AllProvidersExhaustedError(
            f"All configured free providers ({attempted_providers}) failed or have exhausted keys. "
            "Please verify your API keys in .env or run local Ollama."
        )

    async def stream(
        self,
        messages: List[Dict[str, str]],
        preferred_provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]:
        """Streaming generation with automatic provider failover."""
        priority_list = self.get_provider_priority()
        if preferred_provider and preferred_provider in priority_list:
            priority_list.remove(preferred_provider)
            priority_list.insert(0, preferred_provider)

        for provider in priority_list:
            adapter = self.adapters.get(provider)
            if not adapter:
                continue

            try:
                self._verify_free_only(provider, model)
            except CostProtectionError:
                continue

            is_local = (provider == "ollama")
            while True:
                key_info = None if is_local else self.key_manager.get_available_key(provider)
                if not is_local and not key_info:
                    break

                raw_key = key_info.key if key_info else None
                try:
                    async for token in adapter.stream(
                        messages=messages,
                        api_key=raw_key,
                        model=model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    ):
                        yield token
                    if key_info and raw_key:
                        self.key_manager.mark_success(provider, raw_key)
                    return
                except RateLimitError as e:
                    if key_info and raw_key:
                        self.key_manager.mark_rate_limited(provider, raw_key, retry_after=e.retry_after)
                    continue
                except (QuotaExhaustedError, AuthError, ServerError):
                    if key_info and raw_key:
                        self.key_manager.mark_invalid(provider, raw_key)
                    break
                except Exception:
                    break

        yield "I apologize, sir. All neural language pathways and free providers are currently exhausted or unavailable."

    def get_router_status(self) -> Dict[str, Any]:
        """Provides telemetry for HUD and diagnostic logs."""
        provider_stats = {
            p: self.key_manager.get_provider_status(p)
            for p in self.get_provider_priority()
        }
        return {
            "active_provider": self.active_provider,
            "active_model": self.active_model,
            "active_key": self.active_key_masked,
            "active_key_masked": self.active_key_masked,
            "free_only_mode": self.settings.free_only_mode,
            "priority": self.get_provider_priority(),
            "providers": provider_stats,
            "key_manager": provider_stats,
        }

    get_telemetry = get_router_status
