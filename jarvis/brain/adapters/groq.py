"""
JARVIS AI - Groq Provider Adapter
Connects to Groq's ultra-low latency OpenAI-compatible API for fast response generation.
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
    ContextLengthError,
    ServerError,
    ProviderError,
)
from config.settings import mask_key

logger = logging.getLogger("JARVIS.Adapter.Groq")


class GroqAdapter(BaseProviderAdapter):
    def __init__(
        self,
        base_url: str = "https://api.groq.com/openai/v1",
        default_model: str = "openai/gpt-oss-120b",
        allowed_free_models: Optional[List[str]] = None,
        timeout: float = 15.0,
    ):
        allowed = allowed_free_models or [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
            "qwen/qwen3.8-27b",
            "mixtral-8x7b-32768",
        ]
        super().__init__("groq", base_url, default_model, allowed)
        self.timeout = timeout

    def _get_headers(self, api_key: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _parse_error_response(self, response: httpx.Response, body_json: Dict[str, Any]) -> Exception:
        status = response.status_code
        err_data = body_json.get("error", {})
        err_msg = err_data.get("message", response.text) if isinstance(err_data, dict) else str(err_data)

        if status == 429:
            retry_after_hdr = response.headers.get("retry-after")
            retry_sec = float(retry_after_hdr) if retry_after_hdr and retry_after_hdr.isdigit() else None
            lower = err_msg.lower()
            if "quota" in lower or "limit reached" in lower:
                return QuotaExhaustedError(f"Groq quota limit reached: {err_msg}", provider=self.name)
            return RateLimitError(f"Groq rate limit (TPM/RPM): {err_msg}", retry_after=retry_sec, provider=self.name)

        if status in (401, 403):
            return AuthError(f"Groq authentication error: {err_msg}", provider=self.name)

        if "context length" in err_msg.lower() or "too many tokens" in err_msg.lower():
            return ContextLengthError(f"Groq context limit exceeded: {err_msg}", provider=self.name)

        if status >= 500:
            return ServerError(f"Groq server error ({status}): {err_msg}", provider=self.name, status_code=status)

        return ProviderError(f"Groq error ({status}): {err_msg}", provider=self.name, status_code=status)

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
            raise AuthError("Groq API key is required but none provided.", provider=self.name)

        target_model = model or self.default_model
        payload: Dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools

        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = self._get_headers(api_key)
        client = self._get_client(self.timeout)

        try:
            response = await client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as e:
            raise ServerError(f"Groq request timed out: {str(e)}", provider=self.name)
        except httpx.NetworkError as e:
            raise ServerError(f"Groq network error: {str(e)}", provider=self.name)

        try:
            body = response.json()
        except Exception:
            body = {"raw_text": response.text}

        if response.status_code != 200:
            raise self._parse_error_response(response, body)

        choice = body.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content") or ""
        tool_calls = message.get("tool_calls")
        finish_reason = choice.get("finish_reason")
        usage = body.get("usage", {})

        return LLMResponse(
            content=content,
            model=body.get("model", target_model),
            provider=self.name,
            key_masked=mask_key(api_key),
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=usage,
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
        if not api_key:
            raise AuthError("Groq API key is required but none provided.", provider=self.name)

        target_model = model or self.default_model
        payload = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = self._get_headers(api_key)
        client = self._get_client(self.timeout)

        async with client.stream("POST", url, json=payload, headers=headers) as response:
            if response.status_code != 200:
                body_text = await response.aread()
                try:
                    body_json = json.loads(body_text)
                except Exception:
                    body_json = {"error": {"message": body_text.decode("utf-8", "ignore")}}
                raise self._parse_error_response(response, body_json)

            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        token = delta.get("content")
                        if token:
                            yield token
                    except Exception:
                        continue
