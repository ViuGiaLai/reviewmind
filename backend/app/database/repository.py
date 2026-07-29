from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.review.models import Issue, ReviewResult, Severity


class ReviewRepository:
    """Local SQLite adapter with expanded schema for documents, issues, and history."""

    def __init__(self, database_path: Path):
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------
    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS documents (
                    id              TEXT PRIMARY KEY,
                    original_name   TEXT NOT NULL,
                    content_type    TEXT NOT NULL DEFAULT '',
                    size            INTEGER NOT NULL DEFAULT 0,
                    storage_path    TEXT NOT NULL DEFAULT '',
                    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS review_sessions (
                    id              TEXT PRIMARY KEY,
                    document_id     TEXT REFERENCES documents(id) ON DELETE SET NULL,
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
                    id              TEXT PRIMARY KEY,
                    session_id      TEXT NOT NULL REFERENCES review_sessions(id) ON DELETE CASCADE,
                    issue_id        TEXT NOT NULL,
                    category        TEXT NOT NULL,
                    rule_id         TEXT NOT NULL,
                    severity        TEXT NOT NULL,
                    message         TEXT NOT NULL,
                    recommendation  TEXT NOT NULL DEFAULT '',
                    evidence_excerpt TEXT NOT NULL DEFAULT '',
                    evidence_line_start INTEGER NOT NULL DEFAULT 1,
                    evidence_line_end   INTEGER NOT NULL DEFAULT 1,
                    evidence_location   TEXT NOT NULL DEFAULT '',
                    confidence      INTEGER NOT NULL DEFAULT 0,
                    source          TEXT NOT NULL DEFAULT 'rule',
                    autofix_allowed INTEGER NOT NULL DEFAULT 0,
                    status          TEXT NOT NULL DEFAULT 'open',
                    resolved_at     TEXT,
                    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
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
                    line_start      INTEGER NOT NULL DEFAULT 1,
                    line_end        INTEGER NOT NULL DEFAULT 1,
                    patched_document TEXT NOT NULL DEFAULT '',
                    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
                    reverted_at     TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_issues_session ON issues(session_id);
                CREATE INDEX IF NOT EXISTS idx_issues_status ON issues(status);
                CREATE INDEX IF NOT EXISTS idx_sessions_document ON review_sessions(document_id);
                CREATE INDEX IF NOT EXISTS idx_sessions_created ON review_sessions(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_autofix_session ON autofix_actions(session_id);
            """)

    # ------------------------------------------------------------------
    # Documents
    # ------------------------------------------------------------------
    def save_document(self, original_name: str, content_type: str, size: int, storage_path: str) -> str:
        doc_id = str(uuid4())
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO documents (id, original_name, content_type, size, storage_path) VALUES (?, ?, ?, ?, ?)",
                (doc_id, original_name, content_type, size, storage_path),
            )
        return doc_id

    def get_document(self, doc_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # Review Sessions
    # ------------------------------------------------------------------
    def save_session(
        self,
        filename: str,
        profile_id: str,
        pack_ids: list[str],
        categories: list[str],
        result: ReviewResult,
        document_id: str | None = None,
    ) -> str:
        session_id = str(uuid4())
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO review_sessions
                   (id, document_id, filename, profile_id, pack_ids, categories, status,
                    score, category_scores, summary, report_markdown)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    session_id,
                    document_id,
                    filename,
                    profile_id,
                    json.dumps(pack_ids, ensure_ascii=False),
                    json.dumps(categories, ensure_ascii=False),
                    "completed",
                    result.score,
                    json.dumps(result.category_scores, ensure_ascii=False),
                    result.summary,
                    result.report_markdown,
                ),
            )
            # Save issues in the same transaction
            for issue in result.issues:
                connection.execute(
                    """INSERT INTO issues
                       (id, session_id, issue_id, category, rule_id, severity, message,
                        recommendation, evidence_excerpt, evidence_line_start, evidence_line_end,
                        evidence_location, confidence, source, autofix_allowed, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        str(uuid4()),
                        session_id,
                        issue.id,
                        issue.category,
                        issue.rule_id,
                        issue.severity.value,
                        issue.message,
                        issue.recommendation,
                        issue.evidence.excerpt,
                        issue.evidence.line_start,
                        issue.evidence.line_end,
                        issue.evidence.location,
                        issue.confidence,
                        issue.source,
                        1 if issue.autofix_allowed else 0,
                        "open",
                    ),
                )
        return session_id

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM review_sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["pack_ids"] = json.loads(data.get("pack_ids", "[]"))
        data["categories"] = json.loads(data.get("categories", "[]"))
        data["category_scores"] = json.loads(data.get("category_scores", "{}"))
        return data

    def list_sessions(
        self,
        profile_id: str | None = None,
        document_id: str | None = None,
        status: str | None = None,
        score_min: int | None = None,
        score_max: int | None = None,
        search: str | None = None,
        limit: int = 30,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        conditions: list[str] = []
        params: list[Any] = []

        if profile_id:
            conditions.append("s.profile_id = ?")
            params.append(profile_id)
        if document_id:
            conditions.append("s.document_id = ?")
            params.append(document_id)
        if status:
            conditions.append("s.status = ?")
            params.append(status)
        if score_min is not None:
            conditions.append("s.score >= ?")
            params.append(score_min)
        if score_max is not None:
            conditions.append("s.score <= ?")
            params.append(score_max)
        if search:
            conditions.append("(s.filename LIKE ? OR s.summary LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])

        where = " AND ".join(conditions) if conditions else "1=1"

        with self._connect() as connection:
            count_row = connection.execute(
                f"SELECT COUNT(*) as cnt FROM review_sessions s WHERE {where}", params
            ).fetchone()
            total = count_row["cnt"] if count_row else 0

            rows = connection.execute(
                f"""SELECT s.id, s.created_at, s.filename, s.profile_id, s.status,
                           s.score, s.summary, s.document_id
                    FROM review_sessions s
                    WHERE {where}
                    ORDER BY s.created_at DESC
                    LIMIT ? OFFSET ?""",
                [*params, limit, offset],
            ).fetchall()

        sessions = []
        for row in rows:
            session = dict(row)
            sessions.append(session)
        return sessions, total

    def delete_session(self, session_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM review_sessions WHERE id = ?", (session_id,))
            return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Issues
    # ------------------------------------------------------------------
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
    ) -> tuple[list[dict[str, Any]], int]:
        conditions: list[str] = ["i.session_id = ?"]
        params: list[Any] = [session_id]

        if severity:
            conditions.append("i.severity = ?")
            params.append(severity)
        if category:
            conditions.append("i.category = ?")
            params.append(category)
        if status:
            conditions.append("i.status = ?")
            params.append(status)
        if rule_id:
            conditions.append("i.rule_id = ?")
            params.append(rule_id)
        if search:
            conditions.append("(i.message LIKE ? OR i.recommendation LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])

        where = " AND ".join(conditions)

        with self._connect() as connection:
            count_row = connection.execute(
                f"SELECT COUNT(*) as cnt FROM issues i WHERE {where}", params
            ).fetchone()
            total = count_row["cnt"] if count_row else 0

            rows = connection.execute(
                f"""SELECT i.* FROM issues i
                    WHERE {where}
                    ORDER BY
                        CASE i.severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 WHEN 'low' THEN 2 END,
                        i.created_at DESC
                    LIMIT ? OFFSET ?""",
                [*params, limit, offset],
            ).fetchall()

        issues = [dict(row) for row in rows]
        return issues, total

    def get_issue(self, issue_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM issues WHERE id = ?", (issue_id,)).fetchone()
        return dict(row) if row else None

    def update_issue_status(self, issue_id: str, status: str) -> bool:
        resolved_at = datetime.now(timezone.utc).isoformat() if status in ("resolved", "ignored") else None
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE issues SET status = ?, resolved_at = COALESCE(?, resolved_at) WHERE id = ?",
                (status, resolved_at, issue_id),
            )
            return cursor.rowcount > 0

    def bulk_update_issue_status(self, session_id: str, status: str, category: str | None = None) -> int:
        conditions = ["session_id = ?"]
        params: list[Any] = [session_id]
        if category:
            conditions.append("category = ?")
            params.append(category)
        resolved_at = datetime.now(timezone.utc).isoformat() if status in ("resolved", "ignored") else None
        with self._connect() as connection:
            cursor = connection.execute(
                f"UPDATE issues SET status = ?, resolved_at = COALESCE(?, resolved_at) WHERE {' AND '.join(conditions)}",
                [status, resolved_at, *params],
            )
            return cursor.rowcount

    # ------------------------------------------------------------------
    # Issue history (across sessions for same issue_id pattern)
    # ------------------------------------------------------------------
    def get_issue_history(self, issue_id_pattern: str, session_id: str) -> list[dict[str, Any]]:
        """Find similar issues across sessions for the same document."""
        with self._connect() as connection:
            # Find the document for this session
            row = connection.execute(
                "SELECT document_id FROM review_sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if not row or not row["document_id"]:
                return []

            # Find issues with same issue_id in other sessions for same document
            rows = connection.execute(
                """SELECT i.*, s.created_at as session_created_at, s.score as session_score
                   FROM issues i
                   JOIN review_sessions s ON s.id = i.session_id
                   WHERE s.document_id = ? AND i.issue_id = ? AND i.session_id != ?
                   ORDER BY s.created_at DESC""",
                (row["document_id"], issue_id_pattern, session_id),
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Sessions for a document
    # ------------------------------------------------------------------
    def get_sessions_for_document(self, document_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT id, created_at, profile_id, status, score, summary
                   FROM review_sessions WHERE document_id = ?
                   ORDER BY created_at DESC""",
                (document_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Packs
    # ------------------------------------------------------------------
    def list_packs(self) -> list[dict[str, Any]]:
        """Return all available knowledge packs from config."""
        from pathlib import Path
        import yaml

        packs_dir = Path(__file__).resolve().parents[2] / "config" / "packs"
        results: list[dict[str, Any]] = []
        if packs_dir.is_dir():
            for pack_file in sorted(packs_dir.glob("*/pack.yaml")):
                try:
                    data = yaml.safe_load(pack_file.read_text(encoding="utf-8"))
                    results.append({
                        "id": data.get("id", pack_file.parent.name),
                        "name": data.get("name", pack_file.parent.name),
                        "profile": data.get("profile", ""),
                        "description": data.get("description", ""),
                    })
                except Exception:
                    pass
        return results

    # ------------------------------------------------------------------
    # Autofix Actions
    # ------------------------------------------------------------------
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
        patched_document: str | None = None,
    ) -> str:
        """Save an autofix action (apply or revert)."""
        action_id = str(uuid4())
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO autofix_actions
                   (id, session_id, suggestion_id, issue_id, rule_id, action_type,
                    original_text, patched_text, line_start, line_end, patched_document)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (action_id, session_id, suggestion_id, issue_id, rule_id, action_type,
                 original_text, patched_text, line_start, line_end, patched_document),
            )
        return action_id

    def get_applied_suggestions(self, session_id: str) -> list[dict[str, Any]]:
        """Get all actively applied suggestions (not reverted) for a session."""
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM autofix_actions
                   WHERE session_id = ? AND action_type = 'apply' AND reverted_at IS NULL
                   ORDER BY created_at DESC""",
                (session_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_autofix_history(self, session_id: str) -> list[dict[str, Any]]:
        """Get the complete autofix history for a session."""
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM autofix_actions
                   WHERE session_id = ?
                   ORDER BY created_at DESC""",
                (session_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def revert_autofix_action(self, action_id: str, patched_document: str | None = None) -> bool:
        """Mark an autofix action as reverted. Preserves the original 'apply' record."""
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE autofix_actions
                   SET reverted_at = datetime('now'), patched_document = COALESCE(?, patched_document)
                   WHERE id = ? AND action_type = 'apply' AND reverted_at IS NULL""",
                (patched_document, action_id),
            )
            return cursor.rowcount > 0

    def get_autofix_versions(self, session_id: str) -> list[dict[str, Any]]:
        """Get version history for a session."""
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT id, created_at as created_at,
                          'apply' as action_type,
                          rule_id, line_start, line_end,
                          original_text, patched_text
                   FROM autofix_actions
                   WHERE session_id = ? AND action_type = 'apply'
                   ORDER BY created_at ASC""",
                (session_id,),
            ).fetchall()
        return [dict(r) for r in rows]
