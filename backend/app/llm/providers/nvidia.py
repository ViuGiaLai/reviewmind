from __future__ import annotations

import json
import time
from typing import Any

import httpx

from .base import BaseLLMProvider, LLMResponse, LLMError, AuthError


class NVIDIAProvider(BaseLLMProvider):
    """NVIDIA AI Foundry provider — free tier with Llama, Mixtral, and other open models.
    
    API: https://build.nvidia.com/
    Docs: OpenAI-compatible (use same format as OpenAI API)
    """

    BASE_URL = "https://integrate.api.nvidia.com/v1"

    @property
    def provider_name(self) -> str:
        return "nvidia"

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        if not self.api_key:
            raise AuthError("NVIDIA API key not configured", provider="nvidia")

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
            raise AuthError("Invalid NVIDIA API key", provider="nvidia", status_code=401)
        if resp.status_code == 429:
            from .base import RateLimitError
            raise RateLimitError("NVIDIA rate limit exceeded", provider="nvidia", status_code=429)
        if resp.status_code != 200:
            raise LLMError(f"NVIDIA API error: {resp.text}", provider="nvidia", status_code=resp.status_code)

        data = resp.json()
        choice = data.get("choices", [{}])[0]
        text = choice.get("message", {}).get("content", "")
        usage = data.get("usage", {})

        return LLMResponse(
            text=text,
            model=data.get("model", self.model),
            provider="nvidia",
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
            prompt=f"{prompt}\n\nRespond in valid JSON only. Schema:\n{json.dumps(output_schema, indent=2)}",
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=8192,
        )
        try:
            return json.loads(resp.text)
        except json.JSONDecodeError:
            raise LLMError(f"NVIDIA returned non-JSON: {resp.text[:200]}", provider="nvidia")
