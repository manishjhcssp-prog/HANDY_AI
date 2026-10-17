"""
JARVIS AI - Base Provider Adapter & Normalized Response Interfaces
Defines common response structures, exception hierarchy, and abstract adapter contracts.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, AsyncIterator
from dataclasses import dataclass, field


class ProviderError(Exception):
    """Base exception for all provider issues."""
    def __init__(self, message: str, provider: str = "", status_code: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.status_code = status_code


class RateLimitError(ProviderError):
    """Triggered on HTTP 429 or rate-limit warnings."""
    def __init__(self, message: str, retry_after: Optional[float] = None, provider: str = ""):
        super().__init__(message, provider=provider, status_code=429)
        self.retry_after = retry_after


class QuotaExhaustedError(ProviderError):
    """Triggered when monthly/daily balance or credit limit is reached."""
    def __init__(self, message: str, provider: str = ""):
        super().__init__(message, provider=provider, status_code=429)


class AuthError(ProviderError):
    """Triggered on HTTP 401/403 invalid key or unauthorized access."""
    def __init__(self, message: str, provider: str = ""):
        super().__init__(message, provider=provider, status_code=401)


class ModelNotFoundError(ProviderError):
    """Triggered when the requested model is not found or unsupported."""
    pass


class ContextLengthError(ProviderError):
    """Triggered when context window limit is exceeded."""
    pass


class ServerError(ProviderError):
    """Triggered on 5xx errors from the provider endpoint."""
    pass


@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str
    key_masked: str = ""
    tool_calls: Optional[List[Dict[str, Any]]] = None
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, int]] = field(default_factory=dict)
    raw: Optional[Any] = None


class BaseProviderAdapter(ABC):
    """Abstract base class for all LLM provider adapters."""

    def __init__(self, name: str, base_url: str, default_model: str, allowed_free_models: List[str]):
        self.name = name
        self.base_url = base_url
        self.default_model = default_model
        self.allowed_free_models = allowed_free_models

    def is_free_eligible(self, model: Optional[str]) -> bool:
        """Verifies if the specified model is in the approved free-tier list."""
        target = model or self.default_model
        if ":free" in target or target == "openrouter/free":
            return True
        return target in self.allowed_free_models

    @abstractmethod
    async def generate(
        self,
        messages: List[Dict[str, str]],
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """Executes a single completion and returns a normalized LLMResponse."""
        pass

    @abstractmethod
    async def stream(
        self,
        messages: List[Dict[str, str]],
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]:
        """Streams text chunks token by token for ultra-fast voice output."""
        pass
