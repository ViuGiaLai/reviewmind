from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from app.config import settings

from .config import LLMConfig, ProviderType, MODEL_CATALOG
from .providers import (
    BaseLLMProvider, LLMResponse, LLMError, RateLimitError,
    GeminiProvider, OpenRouterProvider, GitHubModelsProvider,
    NVIDIAProvider, CohereProvider,
    OpenAIProvider, AnthropicProvider,
)

logger = logging.getLogger(__name__)


@dataclass
class RouteResult:
    """Result of routing a request through the provider chain."""
    response: LLMResponse | None = None
    provider_used: str = ""
    model_used: str = ""
    attempts: list[dict[str, Any]] = field(default_factory=list)
    success: bool = False
    error: str = ""


class LLMRouter:
    """Routes requests through available providers with priority, fallback, and cooldown."""

    GEMINI_RPM_LIMIT = 10  # Gemini free tier: ~10 requests per minute

    def __init__(self):
        self._providers: dict[ProviderType, BaseLLMProvider] = {}
        self._cooldowns: dict[ProviderType, float] = {}  # provider -> cooldown until (time.monotonic)
        self._preferred_fallback: ProviderType | None = None  # cached working provider

    def _get_provider(self, provider_type: ProviderType) -> BaseLLMProvider | None:
        """Get or create a provider instance."""
        if provider_type in self._providers:
            return self._providers[provider_type]

        api_key_map = {
            ProviderType.GEMINI: settings.llm.gemini_api_key,
            ProviderType.OPENROUTER: settings.llm.openrouter_api_key,
            ProviderType.GITHUB: settings.llm.github_token,
            ProviderType.NVIDIA: settings.llm.nvidia_api_key,
            ProviderType.COHERE: settings.llm.cohere_api_key,
            ProviderType.OPENAI: settings.llm.openai_api_key,
            ProviderType.ANTHROPIC: settings.llm.anthropic_api_key,
        }

        cls_map = {
            ProviderType.GEMINI: GeminiProvider,
            ProviderType.OPENROUTER: OpenRouterProvider,
            ProviderType.GITHUB: GitHubModelsProvider,
            ProviderType.NVIDIA: NVIDIAProvider,
            ProviderType.COHERE: CohereProvider,
            ProviderType.OPENAI: OpenAIProvider,
            ProviderType.ANTHROPIC: AnthropicProvider,
        }

        # Build model map from MODEL_CATALOG to ensure correctness
        model_map: dict[ProviderType, str] = {}
        for cfg in MODEL_CATALOG.values():
            if cfg.provider not in model_map:
                model_map[cfg.provider] = cfg.id

        cls = cls_map.get(provider_type)
        api_key = api_key_map.get(provider_type, "")
        if not cls or not api_key:
            return None

        provider = cls(
            api_key=api_key,
            model=model_map.get(provider_type, ""),
        )
        if provider.is_available:
            self._providers[provider_type] = provider
            return provider
        return None

    def _is_in_cooldown(self, provider_type: ProviderType) -> bool:
        """Check if a provider is in cooldown (rate-limited)."""
        if provider_type not in self._cooldowns:
            return False
        if time.monotonic() >= self._cooldowns[provider_type]:
            del self._cooldowns[provider_type]
            return False
        return True

    def _mark_cooldown(self, provider_type: ProviderType, seconds: float = 15.0):
        """Put a provider in cooldown for N seconds after rate limit."""
        self._cooldowns[provider_type] = time.monotonic() + seconds
        logger.info(f"Provider {provider_type.value} in cooldown for {seconds}s")

    def _build_priority_list(self, config: LLMConfig) -> list[ProviderType]:
        """Build ordered list of providers to try (free-first, skip cooldowns)."""
        # Primary provider
        ordered = [config.provider]

        # If we have a cached working fallback, prioritize it
        if self._preferred_fallback and self._preferred_fallback not in ordered:
            ordered.append(self._preferred_fallback)

        # Add configured fallbacks
        for fb in config.fallback_providers:
            if fb not in ordered:
                ordered.append(fb)

        # Skip providers in cooldown
        available = []
        skipped = []
        for p in ordered:
            if self._is_in_cooldown(p):
                skipped.append(p)
            else:
                available.append(p)

        if skipped:
            logger.info(f"Skipping providers in cooldown: {[s.value for s in skipped]}")

        return available

    async def route(
        self,
        prompt: str,
        system_prompt: str | None = None,
        config: LLMConfig | None = None,
    ) -> RouteResult:
        """Route a request through providers with fallback and cooldown."""
        cfg = config or LLMConfig()
        priority_list = self._build_priority_list(cfg)

        if not priority_list:
            return RouteResult(
                success=False,
                error="No LLM providers available (all in cooldown or missing API keys). "
                       "Wait a moment and try again, or configure another free provider."
            )

        all_attempts: list[dict[str, Any]] = []

        for provider_type in priority_list:
            provider = self._get_provider(provider_type)
            if not provider:
                all_attempts.append({"provider": provider_type.value, "error": "Provider not available or no API key"})
                continue

            model = cfg.model
            if MODEL_CATALOG.get(cfg.model, {}).provider != provider_type:
                for m in MODEL_CATALOG.values():
                    if m.provider == provider_type:
                        model = m.id
                        break

            for attempt in range(cfg.max_retries):
                try:
                    # Ensure provider uses the correct model (from MODEL_CATALOG)
                    if provider.model != model:
                        provider.model = model
                    logger.info(f"LLM routing: trying {provider_type.value}/{model} (attempt {attempt + 1})")
                    response = await provider.generate(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        temperature=cfg.temperature,
                        max_tokens=cfg.max_tokens,
                    )
                    # Cache this provider as a working fallback for subsequent calls
                    if provider_type != ProviderType.GEMINI:
                        self._preferred_fallback = provider_type
                    result = RouteResult(
                        response=response,
                        provider_used=provider_type.value,
                        model_used=model,
                        attempts=all_attempts + [{"provider": provider_type.value, "model": model, "success": True}],
                        success=True,
                    )
                    logger.info(f"LLM routing: success with {provider_type.value}/{model}")
                    return result
                except RateLimitError:
                    error_msg = f"Rate limit on {provider_type.value}/{model}"
                    logger.warning(f"LLM routing: {error_msg}")
                    all_attempts.append({
                        "provider": provider_type.value,
                        "model": model,
                        "attempt": attempt + 1,
                        "error": error_msg,
                    })
                    # On rate limit, cool down and skip remaining retries for this provider
                    self._mark_cooldown(provider_type, seconds=12.0)
                    break  # Skip remaining retries, move to next provider
                except Exception as e:
                    error_msg = str(e)
                    logger.debug(f"LLM routing: {provider_type.value}/{model} failed: {error_msg}")
                    all_attempts.append({
                        "provider": provider_type.value,
                        "model": model,
                        "attempt": attempt + 1,
                        "error": error_msg,
                    })
                    if attempt < cfg.max_retries - 1:
                        await asyncio.sleep(cfg.retry_delay_seconds * (attempt + 1))

        return RouteResult(
            success=False,
            attempts=all_attempts,
            error=f"All providers failed. Last error: {all_attempts[-1].get('error', 'Unknown')}" if all_attempts else "No providers available.",
        )

    def get_stats(self) -> dict[str, Any]:
        """Get router statistics."""
        now = time.monotonic()
        return {
            "providers_initialized": list(self._providers.keys()),
            "provider_count": len(self._providers),
            "cooldowns": {k.value: max(0, v - now) for k, v in self._cooldowns.items()},
            "preferred_fallback": self._preferred_fallback.value if self._preferred_fallback else None,
        }

    def reset_stats(self) -> None:
        """Reset router statistics."""
        self._providers.clear()
        self._cooldowns.clear()
        self._preferred_fallback = None

    async def route_structured(
        self,
        prompt: str,
        output_schema: dict[str, Any],
        system_prompt: str | None = None,
        config: LLMConfig | None = None,
    ) -> RouteResult:
        """Route a structured output request."""
        cfg = config or LLMConfig()
        cfg.temperature = 0.1

        result = await self.route(
            prompt=f"{prompt}\n\nIMPORTANT: Respond with valid JSON only, matching the provided schema.",
            system_prompt=system_prompt,
            config=cfg,
        )
        return result



