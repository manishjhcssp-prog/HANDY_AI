"""
JARVIS AI - Ollama Local Offline Provider Adapter
Connects to local Ollama service for 100% private, free offline intelligence.
"""

import json
import logging
from typing import Dict, List, Optional, Any, AsyncIterator
import httpx
from .base import (
    BaseProviderAdapter,
    LLMResponse,
    ServerError,
    ModelNotFoundError,
    ProviderError,
)

logger = logging.getLogger("JARVIS.Adapter.Ollama")


class OllamaAdapter(BaseProviderAdapter):
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        default_model: str = "llama3",
        allowed_free_models: Optional[List[str]] = None,
        timeout: float = 30.0,
    ):
        allowed = allowed_free_models or ["llama3", "mistral", "phi3", "qwen2.5", "codellama"]
        super().__init__("ollama", base_url, default_model, allowed)
        self.timeout = timeout

    def is_free_eligible(self, model: Optional[str]) -> bool:
        # All local models running on user's machine are free
        return True

    async def generate(
        self,
        messages: List[Dict[str, str]],
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        target_model = model or self.default_model
        payload = {
            "model": target_model,
            "messages": messages,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
            "stream": False,
        }
        url = f"{self.base_url.rstrip('/')}/api/chat"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, json=payload)
            except httpx.ConnectError:
                raise ServerError("Ollama service is not running locally on http://localhost:11434", provider=self.name)
            except httpx.TimeoutException as e:
                raise ServerError(f"Ollama request timed out: {str(e)}", provider=self.name)
            except Exception as e:
                raise ServerError(f"Ollama connection error: {str(e)}", provider=self.name)

        if response.status_code == 404:
            raise ModelNotFoundError(f"Model '{target_model}' not found in local Ollama library.", provider=self.name)

        if response.status_code != 200:
            raise ProviderError(f"Ollama error ({response.status_code}): {response.text}", provider=self.name)

        body = response.json()
        message = body.get("message", {})
        content = message.get("content", "")

        return LLMResponse(
            content=content,
            model=target_model,
            provider=self.name,
            key_masked="local-offline",
            raw=body,
        )

    async def stream(
        self,
        messages: List[Dict[str, str]],
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]:
        target_model = model or self.default_model
        payload = {
            "model": target_model,
            "messages": messages,
            "options": {"temperature": temperature, "num_predict": max_tokens},
            "stream": True,
        }
        url = f"{self.base_url.rstrip('/')}/api/chat"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                async with client.stream("POST", url, json=payload) as response:
                    if response.status_code != 200:
                        raise ProviderError(f"Ollama error ({response.status_code})", provider=self.name)
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                            token = chunk.get("message", {}).get("content")
                            if token:
                                yield token
                        except Exception:
                            continue
            except httpx.ConnectError:
                raise ServerError("Ollama is not running locally.", provider=self.name)
