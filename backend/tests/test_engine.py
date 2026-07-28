from app.review import ReviewEngine, ReviewRequest


def test_academic_document_without_references_is_reported() -> None:
    result = ReviewEngine().review(ReviewRequest(text="# Introduction\nClaim [1].", profile_id="academic"))
    assert any(issue.rule_id == "citation.reference-list" for issue in result.issues)
    assert result.score < 100


def test_sop_does_not_allow_writing_rewrite() -> None:
    result = ReviewEngine().review(ReviewRequest(text="# Purpose\nText\n# Procedure\nText\n# Revision History\nText", profile_id="sop"))
    writing = [issue for issue in result.issues if issue.category == "writing"]
    assert all(not issue.autofix_allowed for issue in writing)
