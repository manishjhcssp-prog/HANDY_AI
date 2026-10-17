"""
JARVIS AI - Google Gemini Provider Adapter
Connects to Google Generative Language REST API with message translation,
streaming support, and error normalization.
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

logger = logging.getLogger("JARVIS.Adapter.Gemini")


class GeminiAdapter(BaseProviderAdapter):
    def __init__(
        self,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        default_model: str = "gemini-2.0-flash",
        allowed_free_models: Optional[List[str]] = None,
        timeout: float = 20.0,
    ):
        allowed = allowed_free_models or [
            "gemini-2.0-flash",
            "gemini-1.5-flash",
            "gemini-1.5-flash-8b",
            "gemini-2.0-flash-exp",
        ]
        super().__init__("gemini", base_url, default_model, allowed)
        self.timeout = timeout

    def _convert_messages(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Converts OpenAI message history into Gemini contents format."""
        system_text = ""
        contents = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_text += content + "\n"
            elif role == "user":
                contents.append({"role": "user", "parts": [{"text": content}]})
            elif role == "assistant":
                contents.append({"role": "model", "parts": [{"text": content}]})

        req: Dict[str, Any] = {"contents": contents}
        if system_text.strip():
            req["systemInstruction"] = {"parts": [{"text": system_text.strip()}]}
        return req

    def _parse_error_response(self, response: httpx.Response, body_json: Dict[str, Any]) -> Exception:
        status = response.status_code
        err_data = body_json.get("error", {})
        err_msg = err_data.get("message", response.text) if isinstance(err_data, dict) else str(err_data)
        err_status = err_data.get("status", "")

        if status == 429 or err_status == "RESOURCE_EXHAUSTED":
            retry_after_hdr = response.headers.get("retry-after")
            retry_sec = float(retry_after_hdr) if retry_after_hdr and retry_after_hdr.isdigit() else None
            lower = err_msg.lower()
            if "quota" in lower or "exhausted" in lower:
                return QuotaExhaustedError(f"Gemini quota exhausted: {err_msg}", provider=self.name)
            return RateLimitError(f"Gemini rate limit: {err_msg}", retry_after=retry_sec, provider=self.name)

        if status in (401, 403) or "API_KEY_INVALID" in err_msg or "PERMISSION_DENIED" in err_status:
            return AuthError(f"Gemini authentication failed: {err_msg}", provider=self.name)

        if "context window" in err_msg.lower():
            return ContextLengthError(f"Gemini context length error: {err_msg}", provider=self.name)

        if status >= 500:
            return ServerError(f"Gemini server error ({status}): {err_msg}", provider=self.name, status_code=status)

        return ProviderError(f"Gemini error ({status}): {err_msg}", provider=self.name, status_code=status)

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
            raise AuthError("Gemini API key is required but none provided.", provider=self.name)

        target_model = model or self.default_model
        payload = self._convert_messages(messages)
        payload["generationConfig"] = {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        }

        url = f"{self.base_url.rstrip('/')}/models/{target_model}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
            except httpx.TimeoutException as e:
                raise ServerError(f"Gemini request timed out: {str(e)}", provider=self.name)
            except httpx.NetworkError as e:
                raise ServerError(f"Gemini network error: {str(e)}", provider=self.name)

        try:
            body = response.json()
        except Exception:
            body = {"raw_text": response.text}

        if response.status_code != 200:
            raise self._parse_error_response(response, body)

        candidates = body.get("candidates", [{}])
        first_cand = candidates[0] if candidates else {}
        content_parts = first_cand.get("content", {}).get("parts", [{}])
        content_text = "".join([p.get("text", "") for p in content_parts])
        finish_reason = first_cand.get("finishReason")
        usage_meta = body.get("usageMetadata", {})

        return LLMResponse(
            content=content_text,
            model=target_model,
            provider=self.name,
            key_masked=mask_key(api_key),
            finish_reason=finish_reason,
            usage={
                "prompt_tokens": usage_meta.get("promptTokenCount", 0),
                "completion_tokens": usage_meta.get("candidatesTokenCount", 0),
                "total_tokens": usage_meta.get("totalTokenCount", 0),
            },
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
            raise AuthError("Gemini API key is required but none provided.", provider=self.name)

        target_model = model or self.default_model
        payload = self._convert_messages(messages)
        payload["generationConfig"] = {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        }

        url = f"{self.base_url.rstrip('/')}/models/{target_model}:streamGenerateContent?key={api_key}&alt=sse"
        headers = {"Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
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
                        try:
                            chunk = json.loads(data_str)
                            cands = chunk.get("candidates", [{}])
                            parts = cands[0].get("content", {}).get("parts", [])
                            for p in parts:
                                txt = p.get("text")
                                if txt:
                                    yield txt
                        except Exception:
                            continue
