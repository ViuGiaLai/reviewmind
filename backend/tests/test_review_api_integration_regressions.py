from dataclasses import dataclass

import pytest
from fastapi import HTTPException


class _FakeDatabase:
    def __init__(self, issue):
        self.issue = issue
        self.updated = False

    def get_issue(self, issue_id):
        return self.issue

    def get_issue_history(self, issue_id, session_id, user_id=None):
        return []

    def update_issue_status(self, issue_id, status):
        self.updated = True
        return True

    def list_issues(self, **kwargs):
        return [self.issue], 1


def test_issue_detail_rejects_issue_from_another_session(monkeypatch):
    from app.api import review

    fake = _FakeDatabase({"id": "issue-1", "issue_id": "rule-1", "session_id": "session-b"})
    monkeypatch.setattr(review, "database", fake)
    monkeypatch.setattr(review, "_verify_session_owner", lambda session_id, user_id: {"id": session_id})

    with pytest.raises(HTTPException) as exc:
        review.get_issue_detail("session-a", "issue-1", "user-1")

    assert exc.value.status_code == 404


def test_issue_update_rejects_issue_from_another_session(monkeypatch):
    from app.api import review

    fake = _FakeDatabase({"id": "issue-1", "issue_id": "rule-1", "session_id": "session-b"})
    monkeypatch.setattr(review, "database", fake)
    monkeypatch.setattr(review, "_verify_session_owner", lambda session_id, user_id: {"id": session_id})

    with pytest.raises(HTTPException) as exc:
        review.update_issue_status(
            "session-a",
            "issue-1",
            review.IssueUpdateBody(status="resolved"),
            "user-1",
        )

    assert exc.value.status_code == 404
    assert fake.updated is False


def test_insights_preserve_autofix_capability(monkeypatch):
    from app.api import review
    from app.review.report.insights import InsightsEngine

    issue = {
        "id": "issue-1",
        "issue_id": "rule-1",
        "session_id": "session-a",
        "category": "writing",
        "severity": "medium",
        "rule_id": "WRITING_001",
        "message": "Improve wording",
        "recommendation": "Use concise wording",
        "autofix_allowed": 1,
        "source": "rule",
    }
    fake = _FakeDatabase(issue)
    monkeypatch.setattr(review, "database", fake)
    monkeypatch.setattr(
        review,
        "_verify_session_owner",
        lambda session_id, user_id: {
            "id": session_id,
            "score": 80,
            "category_scores": {},
            "profile_id": "academic",
        },
    )

    captured = {}

    @dataclass
    class _Report:
        auto_fixable: int

    def fake_generate(self, issues, score, category_scores, profile):
        captured["allowed"] = issues[0].autofix_allowed
        return _Report(auto_fixable=sum(1 for item in issues if item.autofix_allowed))

    monkeypatch.setattr(InsightsEngine, "generate_report", fake_generate)

    response = review.get_session_insights("session-a", "user-1")

    assert captured["allowed"] is True
    assert response["auto_fixable"] == 1


def test_session_owner_rejects_cross_account_and_legacy_rows(monkeypatch):
    from app.api import review

    class FakeSessionDatabase:
        session = None
        def get_session(self, session_id):
            return self.session

    fake = FakeSessionDatabase()
    monkeypatch.setattr(review, "database", fake)
    for session in ({"id": "s1", "user_id": "user-b"}, {"id": "s1", "user_id": None}):
        fake.session = session
        with pytest.raises(HTTPException) as exc:
            review._verify_session_owner("s1", "user-a")
        assert exc.value.status_code == 404


def test_document_detail_rejects_cross_account_before_loading_sessions(monkeypatch):
    from app.api import additional

    class FakeDocumentDatabase:
        sessions_loaded = False
        def get_document(self, doc_id):
            return {"id": doc_id, "user_id": "user-b"}
        def get_sessions_for_document(self, document_id, user_id=None):
            self.sessions_loaded = True
            return []

    fake = FakeDocumentDatabase()
    monkeypatch.setattr(additional, "database", fake)
    with pytest.raises(HTTPException) as exc:
        additional.get_document("doc-1", "user-a")
    assert exc.value.status_code == 404
    assert fake.sessions_loaded is False