from app.review import ReviewEngine
from app.review.models import Evidence, Issue, ReviewRequest, Severity
from app.review.profiles import Profile
from app.review.scoring import ScoreEngine


def _profile() -> Profile:
    return Profile(
        id="academic",
        name="Academic",
        categories=["writing"],
        weights={"writing": 1},
        permissions={"writing": 1},
        required_sections=[],
    )


def _issue() -> Issue:
    return Issue(
        id="issue-1",
        category="writing",
        rule_id="writing.test",
        severity=Severity.MEDIUM,
        message="Test issue",
        recommendation="Fix it",
        evidence=Evidence(excerpt="text", line_start=1, line_end=1, location="line 1"),
        confidence=100,
        source="rule",
        autofix_allowed=True,
    )


def test_review_strictness_changes_real_score_deductions() -> None:
    scorer = ScoreEngine()
    strict, _ = scorer.score([_issue()], _profile(), "strict")
    standard, _ = scorer.score([_issue()], _profile(), "standard")
    relaxed, _ = scorer.score([_issue()], _profile(), "relaxed")

    assert strict < standard < relaxed


def test_custom_profile_overrides_are_reflected_in_review_result() -> None:
    engine = ReviewEngine(enable_ai=False)
    result = engine.review(
        ReviewRequest(
            text="A concise paragraph for a profile integration test.",
            profile_id="academic",
            enabled_categories=["writing"],
            review_mode="rule_only",
            profile_overrides={
                "id": "custom-profile-id",
                "name": "University thesis",
                "categories": ["writing"],
                "weights": {"writing": 1},
            },
            scoring_mode="relaxed",
        )
    )

    assert result.profile_id == "custom-profile-id"
    assert set(result.category_scores) == {"writing"}
    assert result.pipeline_status["profile"]["label"] == "University thesis"
