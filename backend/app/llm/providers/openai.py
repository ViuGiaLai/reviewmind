from __future__ import annotations

import json
import time
from typing import Any

import httpx

from .base import BaseLLMProvider, LLMResponse, LLMError, AuthError


class OpenAIProvider(BaseLLMProvider):
    """OpenAI API provider with structured output support."""

    BASE_URL = "https://api.openai.com/v1"

    @property
    def provider_name(self) -> str:
        return "openai"

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        if not self.api_key:
            raise AuthError("OpenAI API key not configured", provider="openai")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        start = time.time()
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
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
            raise AuthError("Invalid OpenAI API key", provider="openai", status_code=401)
        if resp.status_code == 429:
            from .base import RateLimitError
            raise RateLimitError("OpenAI rate limit exceeded", provider="openai", status_code=429)
        if resp.status_code != 200:
            raise LLMError(f"OpenAI API error: {resp.text}", provider="openai", status_code=resp.status_code)

        data = resp.json()
        choice = data.get("choices", [{}])[0]
        text = choice.get("message", {}).get("content", "")
        usage = data.get("usage", {})

        return LLMResponse(
            text=text,
            model=data.get("model", self.model),
            provider="openai",
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
        """Generate structured output using OpenAI's response_format parameter."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        start = time.time()
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "response_format": {"type": "json_object"},
                },
            )
        elapsed = (time.time() - start) * 1000

        if resp.status_code != 200:
            raise LLMError(f"OpenAI structured API error: {resp.text}", provider="openai", status_code=resp.status_code)

        data = resp.json()
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            raise LLMError(f"OpenAI returned invalid JSON: {text[:200]}", provider="openai")
