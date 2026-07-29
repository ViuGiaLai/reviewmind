from __future__ import annotations

import json
import time
from typing import Any

import httpx

from .base import BaseLLMProvider, LLMResponse, LLMError, AuthError


class OpenRouterProvider(BaseLLMProvider):
    """OpenRouter provider — access many free and paid models."""

    BASE_URL = "https://openrouter.ai/api/v1"

    @property
    def provider_name(self) -> str:
        return "openrouter"

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        if not self.api_key:
            raise AuthError("OpenRouter API key not configured", provider="openrouter")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        start = time.time()
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "https://reviewmind.dev",
                    "X-Title": "ReviewMind",
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
        elapsed = (time.time() - start) * 1000

        if resp.status_code == 401:
            raise AuthError("Invalid OpenRouter API key", provider="openrouter", status_code=401)
        if resp.status_code != 200:
            raise LLMError(f"OpenRouter API error: {resp.text}", provider="openrouter", status_code=resp.status_code)

        data = resp.json()
        choice = data.get("choices", [{}])[0]
        text = choice.get("message", {}).get("content", "")
        usage = data.get("usage", {})

        return LLMResponse(
            text=text,
            model=data.get("model", self.model),
            provider="openrouter",
            usage_input_tokens=usage.get("prompt_tokens", 0),
            usage_output_tokens=usage.get("completion_tokens", 0),
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
            raise LLMError(f"OpenRouter returned non-JSON: {resp.text[:200]}", provider="openrouter")
