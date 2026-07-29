from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.review.models import Issue, ReviewResult, Severity


class DatabaseBackend(ABC):
    """Abstract interface for database operations."""

    @abstractmethod
    def initialize(self) -> None:
        """Initialize the database (create tables/schema if needed)."""
        ...

    # ── Users ─────────────────────────────────────────────────────────────────

    @abstractmethod
    def upsert_user(self, id: str, email: str, name: str, avatar_url: str) -> None: ...

    @abstractmethod
    def get_user(self, id: str) -> dict[str, Any] | None: ...

    # ── Documents ─────────────────────────────────────────────────────────────

    @abstractmethod
    def save_document(self, original_name: str, content_type: str, size: int, storage_path: str, user_id: str | None = None) -> str: ...

    @abstractmethod
    def get_document(self, doc_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    def list_documents(
        self,
        search: str | None = None,
        content_type: str | None = None,
        user_id: str | None = None,
        limit: int = 30,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]: ...

    @abstractmethod
    def delete_document(self, doc_id: str) -> bool: ...

    @abstractmethod
    def save_reference_template(
        self, original_name: str, size: int, storage_path: str,
        analysis: dict[str, Any], user_id: str | None = None,
    ) -> str: ...

    @abstractmethod
    def get_reference_template(self, template_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    def list_reference_templates(self, user_id: str | None = None) -> list[dict[str, Any]]: ...

    @abstractmethod
    def delete_reference_template(self, template_id: str) -> bool: ...

    # Evaluation Profiles

    @abstractmethod
    def create_evaluation_profile(self, user_id: str, data: dict[str, Any]) -> str: ...

    @abstractmethod
    def get_evaluation_profile(self, profile_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    def list_evaluation_profiles(self, user_id: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    def update_evaluation_profile(
        self, profile_id: str, user_id: str, data: dict[str, Any]
    ) -> bool: ...

    @abstractmethod
    def delete_evaluation_profile(self, profile_id: str, user_id: str) -> bool: ...
    # ── Review Sessions ──────────────────────────────────────────────────

    @abstractmethod
    def save_session(
        self,
        filename: str,
        profile_id: str,
        pack_ids: list[str],
        categories: list[str],
        result: ReviewResult,
        document_id: str | None = None,
        user_id: str | None = None,
        reference_template_id: str | None = None,
    ) -> str: ...

    @abstractmethod
    def get_session(self, session_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    def list_sessions(
        self,
        profile_id: str | None = None,
        document_id: str | None = None,
        status: str | None = None,
        score_min: int | None = None,
        score_max: int | None = None,
        search: str | None = None,
        user_id: str | None = None,
        limit: int = 30,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]: ...

    @abstractmethod
    def delete_session(self, session_id: str) -> bool: ...

    # ── Issues ───────────────────────────────────────────────────────────

    @abstractmethod
    def list_issues(
        self,
        session_id: str,
        severity: str | None = None,
        category: str | None = None,
        status: str | None = None,
        rule_id: str | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]: ...

    @abstractmethod
    def get_issue(self, issue_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    def update_issue_status(self, issue_id: str, status: str) -> bool: ...

    @abstractmethod
    def bulk_update_issue_status(self, session_id: str, status: str, category: str | None = None) -> int: ...

    @abstractmethod
    def get_issue_history(self, issue_id_pattern: str, session_id: str, user_id: str | None = None) -> list[dict[str, Any]]: ...

    @abstractmethod
    def get_sessions_for_document(self, document_id: str, user_id: str | None = None) -> list[dict[str, Any]]: ...

    # ── Global Issues ────────────────────────────────────────────────────

    @abstractmethod
    def list_all_issues(
        self,
        severity: str | None = None,
        category: str | None = None,
        status: str | None = None,
        search: str | None = None,
        user_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]: ...

    @abstractmethod
    def get_issue_evidence(self, issue_id: str) -> dict[str, Any] | None: ...

    # ── Aggregation / Dashboard ──────────────────────────────────────────

    @abstractmethod
    def get_dashboard_stats(self, user_id: str | None = None) -> dict[str, Any]: ...

    @abstractmethod
    def get_statistics(self, user_id: str | None = None) -> dict[str, Any]: ...

    # ── History Compare ──────────────────────────────────────────────────

    @abstractmethod
    def compare_sessions(self, session_id_1: str, session_id_2: str) -> dict[str, Any]: ...

    # ── Search ───────────────────────────────────────────────────────────

    @abstractmethod
    def search_all(
        self,
        query: str,
        limit: int = 20,
        user_id: str | None = None,
    ) -> dict[str, list[dict[str, Any]]]: ...

    # ── Packs ────────────────────────────────────────────────────────────

    @abstractmethod
    def list_packs(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    def get_packs_for_profile(self, profile_id: str) -> list[dict[str, Any]]: ...

    # ── Autofix Actions ───────────────────────────────────────────────────

    @abstractmethod
    def save_autofix_action(
        self,
        session_id: str,
        suggestion_id: str,
        issue_id: str,
        rule_id: str,
        action_type: str,
        original_text: str,
        patched_text: str,
        line_start: int,
        line_end: int,
        patched_document: str = "",
    ) -> str: ...

    @abstractmethod
    def get_applied_suggestions(self, session_id: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    def revert_autofix_action(self, action_id: str, reverted_document: str = "") -> bool: ...

    @abstractmethod
    def get_autofix_history(self, session_id: str) -> list[dict[str, Any]]: ...


# ─── SQL Schema (shared between backends) ─────────────────────────────────

# Tables only — safe for executescript even on existing DBs
CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id              TEXT PRIMARY KEY,
    email           TEXT NOT NULL,
    name            TEXT NOT NULL,
    avatar_url      TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS documents (
    id              TEXT PRIMARY KEY,
    user_id         TEXT REFERENCES users(id) ON DELETE CASCADE,
    original_name   TEXT NOT NULL,
    content_type    TEXT NOT NULL DEFAULT '',
    size            INTEGER NOT NULL DEFAULT 0,
    storage_path    TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS reference_templates (
    id              TEXT PRIMARY KEY,
    user_id         TEXT REFERENCES users(id) ON DELETE CASCADE,
    original_name   TEXT NOT NULL,
    size            INTEGER NOT NULL DEFAULT 0,
    storage_path    TEXT NOT NULL DEFAULT '',
    analysis        TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS evaluation_profiles (
    id                    TEXT PRIMARY KEY,
    user_id               TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name                  TEXT NOT NULL,
    description           TEXT NOT NULL DEFAULT '',
    base_profile_id       TEXT NOT NULL DEFAULT 'academic',
    document_types        TEXT NOT NULL DEFAULT '[]',
    knowledge_pack_ids    TEXT NOT NULL DEFAULT '[]',
    reference_template_id TEXT REFERENCES reference_templates(id) ON DELETE SET NULL,
    enabled_categories    TEXT NOT NULL DEFAULT '[]',
    ai_review_enabled     INTEGER NOT NULL DEFAULT 1,
    auto_fix_enabled      INTEGER NOT NULL DEFAULT 0,
    scoring_profile       TEXT NOT NULL DEFAULT 'standard',
    language              TEXT NOT NULL DEFAULT 'vi',
    review_mode           TEXT NOT NULL DEFAULT 'standard',
    visibility            TEXT NOT NULL DEFAULT 'private',
    created_at            TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at            TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS review_sessions (
    id              TEXT PRIMARY KEY,
    user_id         TEXT REFERENCES users(id) ON DELETE CASCADE,
    document_id     TEXT REFERENCES documents(id) ON DELETE SET NULL,
    reference_template_id TEXT REFERENCES reference_templates(id) ON DELETE SET NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    filename        TEXT NOT NULL,
    profile_id      TEXT NOT NULL,
    pack_ids        TEXT NOT NULL DEFAULT '[]',
    categories      TEXT NOT NULL DEFAULT '[]',
    status          TEXT NOT NULL DEFAULT 'completed',
    score           INTEGER NOT NULL DEFAULT 0,
    category_scores TEXT NOT NULL DEFAULT '{}',
    summary         TEXT NOT NULL DEFAULT '',
    report_markdown TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS issues (
    id                  TEXT PRIMARY KEY,
    session_id          TEXT NOT NULL REFERENCES review_sessions(id) ON DELETE CASCADE,
    issue_id            TEXT NOT NULL,
    category            TEXT NOT NULL,
    rule_id             TEXT NOT NULL,
    severity            TEXT NOT NULL,
    message             TEXT NOT NULL,
    recommendation      TEXT NOT NULL DEFAULT '',
    evidence_excerpt    TEXT NOT NULL DEFAULT '',
    evidence_line_start INTEGER NOT NULL DEFAULT 1,
    evidence_line_end   INTEGER NOT NULL DEFAULT 1,
    evidence_location   TEXT NOT NULL DEFAULT '',
    confidence          INTEGER NOT NULL DEFAULT 0,
    source              TEXT NOT NULL DEFAULT 'rule',
    autofix_allowed     INTEGER NOT NULL DEFAULT 0,
    status              TEXT NOT NULL DEFAULT 'open',
    resolved_at         TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS autofix_actions (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES review_sessions(id) ON DELETE CASCADE,
    suggestion_id   TEXT NOT NULL,
    issue_id        TEXT NOT NULL DEFAULT '',
    rule_id         TEXT NOT NULL DEFAULT '',
    action_type     TEXT NOT NULL DEFAULT 'apply',
    original_text   TEXT NOT NULL DEFAULT '',
    patched_text    TEXT NOT NULL DEFAULT '',
    line_start      INTEGER NOT NULL DEFAULT 0,
    line_end        INTEGER NOT NULL DEFAULT 0,
    applied_at      TEXT NOT NULL DEFAULT (datetime('now')),
    reverted_at     TEXT,
    reverted_document TEXT NOT NULL DEFAULT '',
    patched_document  TEXT NOT NULL DEFAULT ''
);
"""

# Indexes — created separately so migration can add missing columns first
CREATE_INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_autofix_session ON autofix_actions(session_id);
CREATE INDEX IF NOT EXISTS idx_autofix_suggestion ON autofix_actions(suggestion_id);
CREATE INDEX IF NOT EXISTS idx_issues_session ON issues(session_id);
CREATE INDEX IF NOT EXISTS idx_issues_status ON issues(status);
CREATE INDEX IF NOT EXISTS idx_sessions_document ON review_sessions(document_id);
CREATE INDEX IF NOT EXISTS idx_sessions_template ON review_sessions(reference_template_id);
CREATE INDEX IF NOT EXISTS idx_sessions_created ON review_sessions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reference_templates_user ON reference_templates(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_evaluation_profiles_user ON evaluation_profiles(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_documents_user_created ON documents(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_user_created ON review_sessions(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_user_profile_created ON review_sessions(user_id, profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_issues_session_status_severity ON issues(session_id, status, severity);
CREATE INDEX IF NOT EXISTS idx_issues_session_rule ON issues(session_id, rule_id);
"""

# Combined for backward compat
CREATE_SCHEMA_SQL = CREATE_TABLES_SQL + CREATE_INDEXES_SQL


# ─── Issue/Result helpers ───────────────────────────────────────────────

def _serialize_issues(result: ReviewResult, session_id: str) -> list[dict[str, Any]]:
    return [
        {
            "id": str(uuid4()),
            "session_id": session_id,
            "issue_id": issue.id,
            "category": issue.category,
            "rule_id": issue.rule_id,
            "severity": issue.severity.value,
            "message": issue.message,
            "recommendation": issue.recommendation,
            "evidence_excerpt": issue.evidence.excerpt,
            "evidence_line_start": issue.evidence.line_start,
            "evidence_line_end": issue.evidence.line_end,
            "evidence_location": issue.evidence.location,
            "confidence": issue.confidence,
            "source": issue.source,
            "autofix_allowed": 1 if issue.autofix_allowed else 0,
            "status": "open",
        }
        for issue in result.issues
    ]


def _parse_session_row(row: dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    if isinstance(data.get("pack_ids"), str):
        data["pack_ids"] = json.loads(data["pack_ids"])
    if isinstance(data.get("categories"), str):
        data["categories"] = json.loads(data["categories"])
    if isinstance(data.get("category_scores"), str):
        data["category_scores"] = json.loads(data["category_scores"])
    return data
