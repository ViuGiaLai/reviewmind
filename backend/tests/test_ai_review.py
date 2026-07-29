import asyncio
from types import SimpleNamespace

from app.llm.ai_review import AIReviewer
from app.llm.prompt_builder import ReviewPromptBuilder
from app.llm.providers.base import LLMResponse
from app.llm.router import RouteResult
from app.review.scheduler import AIReviewScheduler


class FakeRouter:
    def __init__(self) -> None:
        self.prompt = ""
        self.schema = {}

    async def route_structured(self, prompt, output_schema, system_prompt=None, config=None):
        self.prompt = prompt
        self.schema = output_schema
        return RouteResult(
            success=True,
            response=LLMResponse(
                text=(
                    '[{"category":"logic","rule_id":"ai.missing_support",'
                    '"severity":"medium","message":"The conclusion lacks support.",'
                    '"recommendation":"Add evidence before the conclusion.",'
                    '"evidence_excerpt":"Therefore the design is reliable.",'
                    '"confidence":91}]'
                ),
                model="fake",
                provider="fake",
            ),
        )

    def get_stats(self):
        return {}

    def reset_stats(self):
        return None


def _profile(**overrides):
    values = {
        "id": "academic",
        "name": "Academic Review",
        "permissions": {"writing": 3, "logic": 2},
        "ai_focus": ["argument_quality", "coherence"],
        "rubric": {"logic": "Claims are supported by evidence"},
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_scheduler_uses_category_permission_levels() -> None:
    decision = AIReviewScheduler().decide(
        document_text=" ".join(["argument"] * 90),
        profile=_profile(),
        issues=[],
        categories={"writing", "logic"},
        pack_config={},
    )
    assert decision.should_run
    assert "argument_quality" in decision.evaluation_types


def test_prompt_builder_includes_dynamic_document_and_pack_context() -> None:
    built = ReviewPromptBuilder().build_review(
        document_text="Sample document.",
        document_type="journal_article",
        profile=_profile(),
        pack_context={
            "names": ["IEEE 1.0"],
            "rubrics": {"citation": "Use IEEE style"},
            "prompts": {"review": "Check technical novelty"},
            "capabilities": [],
            "checklists": [],
        },
    )
    assert "journal_article" in built.user_prompt
    assert "IEEE 1.0" in built.user_prompt
    assert "argument quality" in built.user_prompt
    assert built.output_schema["type"] == "array"


def test_ai_review_uses_structured_output_and_locates_evidence() -> None:
    router = FakeRouter()
    text = "Introduction\nTherefore the design is reliable.\nConclusion"
    issues = asyncio.run(
        AIReviewer(router=router).analyze_document(
            document_text=text,
            profile=_profile(),
            document_type="technical_spec",
            focus=("argument_quality",),
        )
    )
    assert len(issues) == 1
    assert issues[0].evidence.line_start == 2
    assert router.schema["type"] == "array"
