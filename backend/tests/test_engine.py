from types import SimpleNamespace

from app.review import ReviewEngine, ReviewRequest
from app.review.scheduler import AIReviewScheduler


def test_academic_document_without_references_is_reported() -> None:
    result = ReviewEngine().review(ReviewRequest(text="# Introduction\nClaim [1].", profile_id="academic"))
    assert any(issue.rule_id == "citation.reference-list" for issue in result.issues)
    assert result.score < 100


def test_sop_does_not_allow_writing_rewrite() -> None:
    result = ReviewEngine().review(ReviewRequest(text="# Purpose\nText\n# Procedure\nText\n# Revision History\nText", profile_id="sop"))
    writing = [issue for issue in result.issues if issue.category == "writing"]
    assert all(not issue.autofix_allowed for issue in writing)


def test_ai_scheduler_skips_simple_rule_only_reviews() -> None:
    scheduler = AIReviewScheduler()
    decision = scheduler.decide(
        document_text="# Introduction\nThis is a short document.",
        profile=SimpleNamespace(id="academic", permissions={"rewrite": 1, "explain": 1}),
        issues=[SimpleNamespace(category="writing", rule_id="writing.grammar")],
        categories={"writing"},
        pack_config={},
    )
    assert not decision.should_run
    assert decision.reason


def test_auto_profile_detects_technical_design_documents() -> None:
    text = (
        "# ResearchMind — Document Review Engine\n\n"
        "## Overview\nThis document describes the architecture of the platform.\n\n"
        "## Architecture\nThe system is composed of parser, engine, and UI modules.\n\n"
        "## Components\nThe parser handles uploads and the engine evaluates rules.\n\n"
        "## Configuration\nYAML configuration files define rules and packs."
    )
    result = ReviewEngine().review(ReviewRequest(text=text, profile_id="auto"))
    assert not any(issue.rule_id == "structure.abstract-check" for issue in result.issues)
    assert not any(issue.rule_id == "citation.reference-list" for issue in result.issues)
