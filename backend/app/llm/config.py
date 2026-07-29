from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


class ProviderType(str, Enum):
    GEMINI = "gemini"
    OPENROUTER = "openrouter"
    GITHUB = "github"
    NVIDIA = "nvidia"
    COHERE = "cohere"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


@dataclass
class ModelConfig:
    """Configuration for a specific model within a provider."""
    id: str  # Model identifier (e.g. "gemini-2.0-flash-lite")
    name: str  # Display name
    provider: ProviderType
    max_tokens: int = 4096
    temperature: float = 0.3
    supports_streaming: bool = True
    supports_structured_output: bool = False
    is_free: bool = False
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    context_window: int = 32768
    rate_limit_rpm: int = 60
    rate_limit_tpm: int = 1000000


@dataclass
class LLMConfig:
    """Complete LLM configuration for a session."""
    provider: ProviderType = ProviderType.GEMINI
    model: str = "gemini-2.0-flash-lite"
    temperature: float = 0.3
    max_tokens: int = 4096
    enable_streaming: bool = False
    enable_guardrails: bool = True
    allow_sensitive_data: bool = False

    # Provider-specific overrides
    api_key: str = ""
    api_base: str = ""

    # Fallback chain (ordered list of providers to try when primary fails)
    # All free providers included; ordered by reliability and speed
    fallback_providers: list[ProviderType] = field(default_factory=lambda: [
        ProviderType.GITHUB,
        ProviderType.NVIDIA,
        ProviderType.COHERE,
        ProviderType.OPENROUTER,
    ])

    # Retry
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    timeout_seconds: float = 30.0


# Pre-defined model catalog
MODEL_CATALOG: dict[str, ModelConfig] = {
    # ── Gemini (Free via Google AI Studio) ────────────────────────────────
    "gemini-2.0-flash-lite": ModelConfig(
        id="gemini-2.0-flash-lite",
        name="Gemini 2.0 Flash Lite",
        provider=ProviderType.GEMINI,
        max_tokens=8192,
        temperature=0.3,
        is_free=True,
        context_window=1048576,
    ),
    "gemini-2.0-flash": ModelConfig(
        id="gemini-2.0-flash",
        name="Gemini 2.0 Flash",
        provider=ProviderType.GEMINI,
        max_tokens=8192,
        temperature=0.3,
        is_free=True,
        context_window=1048576,
    ),
    "gemini-1.5-flash": ModelConfig(
        id="gemini-1.5-flash",
        name="Gemini 1.5 Flash",
        provider=ProviderType.GEMINI,
        max_tokens=8192,
        temperature=0.3,
        is_free=True,
        context_window=1048576,
    ),

    # ── OpenRouter (Free models) ──────────────────────────────────────────
    "openrouter/auto": ModelConfig(
        id="openrouter/auto",
        name="OpenRouter Auto",
        provider=ProviderType.OPENROUTER,
        max_tokens=4096,
        temperature=0.3,
        is_free=True,
        context_window=32768,
    ),
    "openrouter/mistral-7b": ModelConfig(
        id="mistralai/mistral-7b-instruct:free",
        name="Mistral 7B (Free)",
        provider=ProviderType.OPENROUTER,
        max_tokens=4096,
        temperature=0.3,
        is_free=True,
        context_window=8192,
    ),

    # ── GitHub Models (Free) ─────────────────────────────────────────────
    "github/gpt-4o-mini": ModelConfig(
        id="gpt-4o-mini",
        name="GPT-4o Mini",
        provider=ProviderType.GITHUB,
        max_tokens=8192,
        temperature=0.3,
        is_free=True,
        context_window=128000,
    ),
    "github/gpt-4o": ModelConfig(
        id="gpt-4o",
        name="GPT-4o",
        provider=ProviderType.GITHUB,
        max_tokens=8192,
        temperature=0.3,
        is_free=True,
        context_window=128000,
    ),

    # ── OpenAI (Paid) ─────────────────────────────────────────────────────
    "gpt-4o-mini": ModelConfig(
        id="gpt-4o-mini",
        name="GPT-4o Mini",
        provider=ProviderType.OPENAI,
        max_tokens=16384,
        temperature=0.3,
        supports_structured_output=True,
        context_window=128000,
    ),
    "gpt-4o": ModelConfig(
        id="gpt-4o",
        name="GPT-4o",
        provider=ProviderType.OPENAI,
        max_tokens=16384,
        temperature=0.3,
        supports_structured_output=True,
        context_window=128000,
    ),

    # ── Anthropic (Paid) ──────────────────────────────────────────────────
    "claude-3-haiku": ModelConfig(
        id="claude-3-haiku-20240307",
        name="Claude 3 Haiku",
        provider=ProviderType.ANTHROPIC,
        max_tokens=4096,
        temperature=0.3,
        context_window=200000,
    ),
    "claude-3.5-sonnet": ModelConfig(
        id="claude-3-5-sonnet-20241022",
        name="Claude 3.5 Sonnet",
        provider=ProviderType.ANTHROPIC,
        max_tokens=8192,
        temperature=0.3,
        context_window=200000,
    ),

    # ── NVIDIA (Free via NVIDIA AI Foundry) ───────────────────────────────
    "nvidia/llama-3.1-8b": ModelConfig(
        id="meta/llama-3.1-8b-instruct",
        name="Llama 3.1 8B Instruct",
        provider=ProviderType.NVIDIA,
        max_tokens=4096,
        temperature=0.3,
        is_free=True,
        context_window=131072,
    ),
    "nvidia/llama-3.1-70b": ModelConfig(
        id="meta/llama-3.1-70b-instruct",
        name="Llama 3.1 70B Instruct",
        provider=ProviderType.NVIDIA,
        max_tokens=4096,
        temperature=0.3,
        is_free=True,
        context_window=131072,
    ),
    "nvidia/mixtral-8x22b": ModelConfig(
        id="mistralai/mixtral-8x22b-instruct-v0.1",
        name="Mixtral 8x22B Instruct",
        provider=ProviderType.NVIDIA,
        max_tokens=4096,
        temperature=0.3,
        is_free=True,
        context_window=65536,
    ),

    # ── Cohere (Free trial) ────────────────────────────────────────────────
    "cohere/command-r": ModelConfig(
        id="command-r",
        name="Command-R",
        provider=ProviderType.COHERE,
        max_tokens=4096,
        temperature=0.3,
        is_free=True,
        context_window=128000,
    ),
    "cohere/command-r-plus": ModelConfig(
        id="command-r-plus",
        name="Command-R+",
        provider=ProviderType.COHERE,
        max_tokens=4096,
        temperature=0.3,
        is_free=True,
        context_window=128000,
    ),
}
