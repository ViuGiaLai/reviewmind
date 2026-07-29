from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider."""
    text: str
    model: str
    provider: str
    finish_reason: str = "stop"
    usage_input_tokens: int = 0
    usage_output_tokens: int = 0
    latency_ms: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)


class LLMError(Exception):
    """Base exception for LLM provider errors."""
    def __init__(self, message: str, provider: str = "", model: str = "", status_code: int = 0):
        self.provider = provider
        self.model = model
        self.status_code = status_code
        super().__init__(message)


class RateLimitError(LLMError):
    """Raised when API rate limit is exceeded."""
    pass


class AuthError(LLMError):
    """Raised when authentication fails."""
    pass


class TimeoutError(LLMError):
    """Raised when request times out."""
    pass


class BaseLLMProvider(ABC):
    """Abstract base class for all LLM providers."""

    def __init__(self, api_key: str = "", model: str = "", config: dict[str, Any] | None = None):
        self.api_key = api_key
        self.model = model
        self.config = config or {}

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Generate a response from the LLM."""
        ...

    async def generate_streaming(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Stream a response from the LLM. Override in subclasses that support streaming."""
        response = await self.generate(prompt, system_prompt, temperature, max_tokens)
        yield response.text

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        output_schema: dict[str, Any],
        system_prompt: str | None = None,
        temperature: float = 0.1,
    ) -> dict[str, Any]:
        """Generate a structured (JSON) response matching the given schema."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name identifier."""
        ...

    @property
    def is_available(self) -> bool:
        """Check if this provider is available (has API key configured)."""
        return bool(self.api_key)

    def _count_tokens(self, text: str) -> int:
        """Rough token count estimation."""
        return len(text.split()) + len(text) // 10
