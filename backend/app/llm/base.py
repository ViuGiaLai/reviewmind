from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider."""

    content: str
    model: str
    provider: str
    finish_reason: str = "stop"
    usage: dict[str, int] = field(default_factory=lambda: {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
    raw: dict[str, Any] | None = None
    cached: bool = False
    latency_ms: float = 0.0


@dataclass
class LLMMessage:
    """A single message in a chat conversation."""

    role: str  # "system", "user", "assistant"
    content: str


class LLMProvider(ABC):
    """Abstract base class for all LLM providers."""

    provider_name: str = ""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    @abstractmethod
    async def generate(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stop_sequences: list[str] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a response from the LLM."""
        ...

    async def generate_stream(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream a response from the LLM (optional override)."""
        response = await self.generate(messages, model, temperature, max_tokens, **kwargs)
        yield response.content

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if the provider is configured and available."""
        ...

    def get_models(self) -> list[str]:
        """Return list of available model names."""
        return []

    def count_tokens(self, text: str) -> int:
        """Estimate token count (rough heuristic)."""
        return len(text.split())

    async def close(self) -> None:
        """Close any open connections. Override in subclasses that use connection pools."""
        pass

    @property
    def supports_streaming(self) -> bool:
        return False

    @property
    def supports_structured_output(self) -> bool:
        return False
