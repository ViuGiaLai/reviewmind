from __future__ import annotations

import json
import time
from typing import Any

import httpx

from .base import BaseLLMProvider, LLMResponse, LLMError, AuthError


class CohereProvider(BaseLLMProvider):
    """Cohere provider — free trial tier with Command-R, Command-R+ models.
    
    API: https://dashboard.cohere.com/
    Docs: https://docs.cohere.com/reference/chat
    """

    BASE_URL = "https://api.cohere.com/v1"

    @property
    def provider_name(self) -> str:
        return "cohere"

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        if not self.api_key:
            raise AuthError("Cohere API key not configured", provider="cohere")

        payload: dict[str, Any] = {
            "model": self.model,
            "message": prompt,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system_prompt:
            payload["preamble"] = system_prompt

        start = time.time()
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.BASE_URL}/chat",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json=payload,
            )
        elapsed = (time.time() - start) * 1000

        if resp.status_code == 401:
            raise AuthError("Invalid Cohere API key", provider="cohere", status_code=401)
        if resp.status_code == 429:
            from .base import RateLimitError
            raise RateLimitError("Cohere rate limit exceeded", provider="cohere", status_code=429)
        if resp.status_code != 200:
            raise LLMError(f"Cohere API error: {resp.text}", provider="cohere", status_code=resp.status_code)

        data = resp.json()
        text = data.get("text", "")
        usage = data.get("meta", {}).get("billed_units", {})

        return LLMResponse(
            text=text,
            model=data.get("model", self.model),
            provider="cohere",
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
            raise LLMError(f"Cohere returned non-JSON: {resp.text[:200]}", provider="cohere")
