import asyncio

from app.config import LLMSettings
from app.llm.router import LLMRouter, RouteResult


def test_openai_key_enables_llm_engine() -> None:
    config = LLMSettings()
    config.gemini_api_key = ""
    config.openrouter_api_key = ""
    config.github_token = ""
    config.nvidia_api_key = ""
    config.cohere_api_key = ""
    config.anthropic_api_key = ""
    config.openai_api_key = "configured"
    assert config.has_any_key


def test_structured_route_embeds_the_actual_json_schema() -> None:
    router = LLMRouter()
    captured = {}

    async def fake_route(prompt, system_prompt=None, config=None):
        captured["prompt"] = prompt
        return RouteResult(success=False, error="test")

    router.route = fake_route
    asyncio.run(
        router.route_structured(
            prompt="Review this.",
            output_schema={"type": "array", "items": {"type": "object"}},
        )
    )
    assert '"type": "array"' in captured["prompt"]
    assert '"type": "object"' in captured["prompt"]
