import pytest
from pydantic import ValidationError

from app.review import ReviewEngine, ReviewRequest
from app.review.report.markdown import render_markdown


def test_review_body_accepts_supported_mode_and_language():
    from app.api.review import ReviewBody
    body = ReviewBody(text="hello", review_mode="full", report_language="vi")
    assert body.review_mode == "full"
    assert body.report_language == "vi"


def test_review_body_rejects_unknown_mode_and_language():
    from app.api.review import ReviewBody
    with pytest.raises(ValidationError):
        ReviewBody(text="hello", review_mode="unknown", report_language="fr")


def test_vietnamese_report_labels_are_rendered():
    report = render_markdown("academic", 92, [], language="vi")
    assert "Báo cáo Chất lượng ReviewMind" in report
    assert "Không phát hiện vấn đề" in report


def test_rules_only_mode_skips_ai_explicitly():
    result = ReviewEngine().review(ReviewRequest(text="# Introduction\nA short document.", review_mode="rule_only"))
    assert result.ai_review_enabled is False
    assert "rules-only" in result.ai_review_reason