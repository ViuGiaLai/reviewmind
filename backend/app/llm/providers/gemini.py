from __future__ import annotations

import json
import time
from typing import Any, AsyncIterator

import httpx

from .base import BaseLLMProvider, LLMResponse, LLMError, AuthError, RateLimitError


class GeminiProvider(BaseLLMProvider):
    """Google Gemini provider using the free Google AI Studio API."""

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    @property
    def provider_name(self) -> str:
        return "gemini"

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        if not self.api_key:
            raise AuthError("Gemini API key not configured", provider="gemini")

        url = f"{self.BASE_URL}/models/{self.model}:generateContent"
        payload: dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        start = time.time()
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                url, params={"key": self.api_key}, json=payload,
            )
        elapsed = (time.time() - start) * 1000

        if resp.status_code == 403:
            raise AuthError("Invalid Gemini API key", provider="gemini", status_code=403)
        if resp.status_code == 429:
            raise RateLimitError("Gemini rate limit exceeded", provider="gemini", status_code=429)
        if resp.status_code != 200:
            raise LLMError(f"Gemini API error: {resp.text}", provider="gemini", status_code=resp.status_code)

        data = resp.json()
        candidates = data.get("candidates", [])
        text = ""
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts)

        usage = data.get("usageMetadata", {})
        return LLMResponse(
            text=text,
            model=self.model,
            provider="gemini",
            usage_input_tokens=usage.get("promptTokenCount", 0),
            usage_output_tokens=usage.get("candidatesTokenCount", 0),
            latency_ms=elapsed,
            raw=data,
        )

    async def generate_structured(
        self,
        prompt: str,
        output_schema: dict[str, Any],
        system_prompt: str | None = None,
        temperature: float = 0.1,
    ) -> dict[str, Any]:
        resp = await self.generate(
            prompt=f"{prompt}\n\nRespond in valid JSON matching this schema:\n{json.dumps(output_schema, indent=2)}",
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=8192,
        )
        try:
            return json.loads(resp.text)
        except json.JSONDecodeError:
            raise LLMError(f"Gemini returned non-JSON response: {resp.text[:200]}", provider="gemini")
