from __future__ import annotations

import json
import time
from typing import Any

import httpx

from .base import BaseLLMProvider, LLMResponse, LLMError, AuthError


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude provider."""

    BASE_URL = "https://api.anthropic.com/v1"

    @property
    def provider_name(self) -> str:
        return "anthropic"

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        if not self.api_key:
            raise AuthError("Anthropic API key not configured", provider="anthropic")

        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            payload["system"] = system_prompt

        start = time.time()
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.BASE_URL}/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        elapsed = (time.time() - start) * 1000

        if resp.status_code == 401:
            raise AuthError("Invalid Anthropic API key", provider="anthropic", status_code=401)
        if resp.status_code != 200:
            raise LLMError(f"Anthropic API error: {resp.text}", provider="anthropic", status_code=resp.status_code)

        data = resp.json()
        text = ""
        content = data.get("content", [])
        for block in content:
            if block.get("type") == "text":
                text += block.get("text", "")

        usage = data.get("usage", {})
        return LLMResponse(
            text=text,
            model=data.get("model", self.model),
            provider="anthropic",
            usage_input_tokens=usage.get("input_tokens", 0),
            usage_output_tokens=usage.get("output_tokens", 0),
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
            prompt=f"{prompt}\n\nRespond in valid JSON only. Schema:\n{json.dumps(output_schema, indent=2)}",
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=8192,
        )
        try:
            return json.loads(resp.text)
        except json.JSONDecodeError:
            raise LLMError(f"Anthropic returned non-JSON: {resp.text[:200]}", provider="anthropic")
