"""
JARVIS AI - OpenRouter Provider Adapter
Connects to OpenRouter.ai API with support for free models (e.g. openai/gpt-oss-20b:free),
streaming responses, rate-limit detection, and error classification.
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

logger = logging.getLogger("JARVIS.Adapter.OpenRouter")


class OpenRouterAdapter(BaseProviderAdapter):
    def __init__(
        self,
        base_url: str = "https://openrouter.ai/api/v1",
        default_model: str = "openrouter/free",
        allowed_free_models: Optional[List[str]] = None,
        timeout: float = 25.0,
    ):
        allowed = allowed_free_models or [
            "openrouter/free",
            "openai/gpt-oss-20b:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "google/gemini-2.0-flash-exp:free",
            "qwen/qwen-2.5-coder-32b-instruct:free",
            "mistralai/mistral-7b-instruct:free",
            "deepseek/deepseek-r1:free",
        ]
        super().__init__("openrouter", base_url, default_model, allowed)
        self.timeout = timeout

    def _get_headers(self, api_key: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://github.com/jarvis-assistant",
            "X-Title": "JARVIS AI Assistant",
            "Content-Type": "application/json",
        }

    def _parse_error_response(self, response: httpx.Response, body_json: Dict[str, Any]) -> Exception:
        status = response.status_code
        err_data = body_json.get("error", {})
        err_msg = err_data.get("message", response.text) if isinstance(err_data, dict) else str(err_data)

        if status == 429:
            retry_after_hdr = response.headers.get("retry-after")
            retry_sec = float(retry_after_hdr) if retry_after_hdr and retry_after_hdr.isdigit() else None
            lower_msg = err_msg.lower()
            if "quota" in lower_msg or "credits" in lower_msg or "exhausted" in lower_msg:
                return QuotaExhaustedError(f"OpenRouter quota exhausted: {err_msg}", provider=self.name)
            return RateLimitError(f"OpenRouter rate limit: {err_msg}", retry_after=retry_sec, provider=self.name)

        if status in (401, 403):
            return AuthError(f"OpenRouter authentication failed: {err_msg}", provider=self.name)

        if "context" in err_msg.lower() or "maximum context" in err_msg.lower():
            return ContextLengthError(f"OpenRouter context exceeded: {err_msg}", provider=self.name)

        if status >= 500:
            return ServerError(f"OpenRouter server error ({status}): {err_msg}", provider=self.name, status_code=status)

        return ProviderError(f"OpenRouter error ({status}): {err_msg}", provider=self.name, status_code=status)

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
            raise AuthError("OpenRouter API key is required but none provided.", provider=self.name)

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
            raise ServerError(f"OpenRouter request timed out: {str(e)}", provider=self.name)
        except httpx.NetworkError as e:
            raise ServerError(f"OpenRouter network connection error: {str(e)}", provider=self.name)

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
            raise AuthError("OpenRouter API key is required but none provided.", provider=self.name)

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
