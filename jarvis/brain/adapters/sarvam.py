"""
JARVIS AI - Sarvam AI Provider Adapter
Connects to Sarvam AI APIs for Indian regional language and Indic speech tasks.
"""

import json
import logging
from typing import Dict, List, Optional, Any, AsyncIterator
import httpx
from .base import (
    BaseProviderAdapter,
    LLMResponse,
    RateLimitError,
    QuotaExhaustedError,
    AuthError,
    ServerError,
    ProviderError,
)
from config.settings import mask_key

logger = logging.getLogger("JARVIS.Adapter.Sarvam")


class SarvamAdapter(BaseProviderAdapter):
    def __init__(
        self,
        base_url: str = "https://api.sarvam.ai",
        default_model: str = "sarvam-105b-conversations",
        allowed_free_models: Optional[List[str]] = None,
        timeout: float = 20.0,
    ):
        allowed = allowed_free_models or [
            "sarvam-105b-conversations",
            "sarvam-105b",
            "sarvam-2b",
            "sarvam-m",
        ]
        super().__init__("sarvam", base_url, default_model, allowed)
        self.timeout = timeout

    def _get_headers(self, api_key: str) -> Dict[str, str]:
        return {
            "api-subscription-key": api_key,
            "Content-Type": "application/json",
        }

    def _parse_error_response(self, response: httpx.Response, body_json: Dict[str, Any]) -> Exception:
        status = response.status_code
        err_msg = body_json.get("message", response.text)

        if status == 429:
            retry_after_hdr = response.headers.get("retry-after")
            retry_sec = float(retry_after_hdr) if retry_after_hdr and retry_after_hdr.isdigit() else None
            lower = str(err_msg).lower()
            if "quota" in lower or "limit" in lower:
                return QuotaExhaustedError(f"Sarvam AI quota exhausted: {err_msg}", provider=self.name)
            return RateLimitError(f"Sarvam AI rate limited: {err_msg}", retry_after=retry_sec, provider=self.name)

        if status in (401, 403):
            return AuthError(f"Sarvam AI authentication failed: {err_msg}", provider=self.name)

        if status >= 500:
            return ServerError(f"Sarvam AI server error ({status}): {err_msg}", provider=self.name, status_code=status)

        return ProviderError(f"Sarvam AI error ({status}): {err_msg}", provider=self.name, status_code=status)

    async def generate(
        self,
        messages: List[Dict[str, str]],
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        if not api_key:
            raise AuthError("Sarvam API key is required but none provided.", provider=self.name)

        target_model = model or self.default_model
        payload = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        url = f"{self.base_url.rstrip('/')}/v1/chat/completions"
        headers = self._get_headers(api_key)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
            except httpx.TimeoutException as e:
                raise ServerError(f"Sarvam AI request timed out: {str(e)}", provider=self.name)
            except httpx.NetworkError as e:
                raise ServerError(f"Sarvam AI network error: {str(e)}", provider=self.name)

        try:
            body = response.json()
        except Exception:
            body = {"raw_text": response.text}

        if response.status_code != 200:
            raise self._parse_error_response(response, body)

        choice = body.get("choices", [{}])[0]
        content = choice.get("message", {}).get("content", "")

        return LLMResponse(
            content=content,
            model=target_model,
            provider=self.name,
            key_masked=mask_key(api_key),
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
        # For endpoints without sse, yield complete generation as stream chunk
        resp = await self.generate(messages, api_key, model, temperature=temperature, max_tokens=max_tokens)
        if resp.content:
            yield resp.content
