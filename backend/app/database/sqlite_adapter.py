from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.review.models import Issue, ReviewResult

from .backend import (
    CREATE_TABLES_SQL,
    DatabaseBackend,
    _parse_session_row,
    _serialize_issues,
)


class SQLiteAdapter(DatabaseBackend):
    """SQLite implementation of the database backend."""

    def __init__(self, database_path: Path):
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

    # ── Connection ────────────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.database_path))
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    # ── Schema ────────────────────────────────────────────────────────────────

    def initialize(self) -> None:
        with self._connect() as connection:
            # Step 1: CREATE TABLE only (safe: IF NOT EXISTS, no index to fail on old schemas)
            connection.executescript(CREATE_TABLES_SQL)

        # Step 2: Check for missing columns in existing tables and migrate
        self._migrate_if_needed()

    def _migrate_if_needed(self) -> None:
        """
        Handle schema migrations for existing databases.
        PRAGMA table_info reveals current columns; missing ones get ALTER TABLE ADD COLUMN.
        """
        migrations: list[tuple[str, str, str]] = [
            # (table, column, type)
            # review_sessions columns added after initial schema
            ("review_sessions", "document_id",     "TEXT REFERENCES documents(id) ON DELETE SET NULL"),
            ("review_sessions", "pack_ids",         "TEXT NOT NULL DEFAULT '[]'"),
            ("review_sessions", "categories",       "TEXT NOT NULL DEFAULT '[]'"),
            ("review_sessions", "status",           "TEXT NOT NULL DEFAULT 'completed'"),
            ("review_sessions", "score",            "INTEGER NOT NULL DEFAULT 0"),
            ("review_sessions", "category_scores",  "TEXT NOT NULL DEFAULT '{}'"),
            ("review_sessions", "summary",          "TEXT NOT NULL DEFAULT ''"),
            ("review_sessions", "report_markdown",  "TEXT NOT NULL DEFAULT ''"),
            # autofix_actions columns added after initial schema
            ("autofix_actions", "issue_id",         "TEXT NOT NULL DEFAULT ''"),
            ("autofix_actions", "rule_id",          "TEXT NOT NULL DEFAULT ''"),
            ("autofix_actions", "action_type",      "TEXT NOT NULL DEFAULT 'apply'"),
            ("autofix_actions", "original_text",    "TEXT NOT NULL DEFAULT ''"),
            ("autofix_actions", "patched_text",     "TEXT NOT NULL DEFAULT ''"),
            ("autofix_actions", "line_start",       "INTEGER NOT NULL DEFAULT 0"),
            ("autofix_actions", "line_end",         "INTEGER NOT NULL DEFAULT 0"),
            ("autofix_actions", "reverted_at",      "TEXT"),
            ("autofix_actions", "reverted_document","TEXT NOT NULL DEFAULT ''"),
            ("autofix_actions", "patched_document", "TEXT NOT NULL DEFAULT ''"),
            # issues columns
            ("issues", "autofix_allowed",           "INTEGER NOT NULL DEFAULT 0"),
            ("issues", "resolved_at",               "TEXT"),
        ]
        with self._connect() as connection:
            for table, col, col_type in migrations:
                existing = {
                    row["name"]
                    for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
                }
                if col not in existing:
                    try:
                        connection.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
                    except Exception:
                        pass  # Skip gracefully if column can't be added

        # Step 3: Create indexes (these may fail if columns were missing before migration)
        # Wrap individually so one failure doesn't block the rest
        index_statements = [
            "CREATE INDEX IF NOT EXISTS idx_autofix_session ON autofix_actions(session_id)",
            "CREATE INDEX IF NOT EXISTS idx_autofix_suggestion ON autofix_actions(suggestion_id)",
            "CREATE INDEX IF NOT EXISTS idx_issues_session ON issues(session_id)",
            "CREATE INDEX IF NOT EXISTS idx_issues_status ON issues(status)",
            "CREATE INDEX IF NOT EXISTS idx_sessions_document ON review_sessions(document_id)",
            "CREATE INDEX IF NOT EXISTS idx_sessions_created ON review_sessions(created_at DESC)",
        ]
        with self._connect() as connection:
            for stmt in index_statements:
                try:
                    connection.execute(stmt)
                except Exception:
                    pass  # Index may already exist or column missing; skip gracefully

    # ── Users ─────────────────────────────────────────────────────────────────

    def upsert_user(self, id: str, email: str, name: str, avatar_url: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO users (id, email, name, avatar_url) 
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT (id) DO UPDATE SET 
                   email = excluded.email, 
                   name = excluded.name, 
                   avatar_url = excluded.avatar_url""",
                (id, email, name, avatar_url)
            )
            conn.commit()

    def get_user(self, id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (id,)).fetchone()
        return dict(row) if row else None

    # ── Documents ─────────────────────────────────────────────────────────────

    def save_document(self, original_name: str, content_type: str, size: int, storage_path: str, user_id: str | None = None) -> str:
        doc_id = str(uuid4())
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO documents (id, user_id, original_name, content_type, size, storage_path) VALUES (?, ?, ?, ?, ?, ?)",
                (doc_id, user_id, original_name, content_type, size, storage_path),
            )
        return doc_id

    def get_document(self, doc_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        return dict(row) if row else None

    def list_documents(
        self,
        search: str | None = None,
        content_type: str | None = None,
        limit: int = 30,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        conditions: list[str] = []
        params: list[Any] = []
        if search:
            conditions.append("(original_name LIKE ? OR id LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        if content_type:
            conditions.append("content_type = ?")
            params.append(content_type)
        where = " AND ".join(conditions) if conditions else "1=1"
        with self._connect() as connection:
            count = connection.execute(f"SELECT COUNT(*) as cnt FROM documents WHERE {where}", params).fetchone()["cnt"]
            rows = connection.execute(
                f"SELECT * FROM documents WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                [*params, limit, offset],
            ).fetchall()
        return [dict(r) for r in rows], count

    def delete_document(self, doc_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            return cursor.rowcount > 0

    # ── Review Sessions ───────────────────────────────────────────────────────

    def save_session(
        self,
        filename: str,
        profile_id: str,
        pack_ids: list[str],
        categories: list[str],
        result: ReviewResult,
        document_id: str | None = None,
        user_id: str | None = None,
    ) -> str:
        session_id = str(uuid4())
        with self._connect() as conn:
            # Detect whether result_json column exists in this DB
            existing_cols = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(review_sessions)").fetchall()
            }
            if "result_json" in existing_cols:
                # Serialize issues to JSON for legacy result_json column (some DBs have it NOT NULL)
                result_json = json.dumps(
                    [{"id": i.id, "severity": i.severity.value, "message": i.message, "rule_id": i.rule_id} for i in result.issues],
                    ensure_ascii=False,
                )
                conn.execute(
                    """INSERT INTO review_sessions
                       (id, user_id, document_id, filename, profile_id, pack_ids, categories, status,
                        score, category_scores, summary, report_markdown, result_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        session_id, user_id, document_id, filename, profile_id,
                        json.dumps(pack_ids, ensure_ascii=False),
                        json.dumps(categories, ensure_ascii=False),
                        "completed", result.score,
                        json.dumps(result.category_scores, ensure_ascii=False),
                        result.summary, result.report_markdown, result_json,
                    ),
                )
            else:
                conn.execute(
                    """INSERT INTO review_sessions
                       (id, user_id, document_id, filename, profile_id, pack_ids, categories, status,
                        score, category_scores, summary, report_markdown)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        session_id, user_id, document_id, filename, profile_id,
                        json.dumps(pack_ids, ensure_ascii=False),
                        json.dumps(categories, ensure_ascii=False),
                        "completed", result.score,
                        json.dumps(result.category_scores, ensure_ascii=False),
                        result.summary, result.report_markdown,
                    ),
                )
            for issue_row in _serialize_issues(result, session_id):
                conn.execute(
                    """INSERT INTO issues
                       (id, session_id, issue_id, category, rule_id, severity, message,
                        recommendation, evidence_excerpt, evidence_line_start, evidence_line_end,
                        evidence_location, confidence, source, autofix_allowed, status)
                       VALUES (:id, :session_id, :issue_id, :category, :rule_id, :severity, :message,
                        :recommendation, :evidence_excerpt, :evidence_line_start, :evidence_line_end,
                        :evidence_location, :confidence, :source, :autofix_allowed, :status)""",
                    issue_row,
                )
        return session_id

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM review_sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            return None
        return _parse_session_row(dict(row))

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

        return [dict(r) for r in rows], total

    def delete_session(self, session_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM review_sessions WHERE id = ?", (session_id,))
            return cursor.rowcount > 0

    # ── Issues ────────────────────────────────────────────────────────────────

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

        return [dict(row) for row in rows], total

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

    def get_issue_history(self, issue_id_pattern: str, session_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT document_id FROM review_sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if not row or not row["document_id"]:
                return []

            rows = connection.execute(
                """SELECT i.*, s.created_at as session_created_at, s.score as session_score
                   FROM issues i
                   JOIN review_sessions s ON s.id = i.session_id
                   WHERE s.document_id = ? AND i.issue_id = ? AND i.session_id != ?
                   ORDER BY s.created_at DESC""",
                (row["document_id"], issue_id_pattern, session_id),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_sessions_for_document(self, document_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT id, created_at, profile_id, status, score, summary
                   FROM review_sessions WHERE document_id = ?
                   ORDER BY created_at DESC""",
                (document_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Global Issues ─────────────────────────────────────────────────────────

    def list_all_issues(
        self,
        severity: str | None = None,
        category: str | None = None,
        status: str | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        conditions: list[str] = []
        params: list[Any] = []
        if severity:
            conditions.append("i.severity = ?"); params.append(severity)
        if category:
            conditions.append("i.category = ?"); params.append(category)
        if status:
            conditions.append("i.status = ?"); params.append(status)
        if search:
            conditions.append("(i.message LIKE ? OR i.recommendation LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        where = " AND ".join(conditions) if conditions else "1=1"
        with self._connect() as connection:
            count = connection.execute(f"SELECT COUNT(*) as cnt FROM issues i WHERE {where}", params).fetchone()["cnt"]
            rows = connection.execute(
                f"""SELECT i.*, s.filename as session_filename, s.profile_id
                   FROM issues i JOIN review_sessions s ON s.id = i.session_id
                   WHERE {where}
                   ORDER BY CASE i.severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                            i.created_at DESC LIMIT ? OFFSET ?""",
                [*params, limit, offset],
            ).fetchall()
        return [dict(r) for r in rows], count

    def get_issue_evidence(self, issue_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT i.id, i.evidence_excerpt, i.evidence_line_start, i.evidence_line_end,
                          i.evidence_location, i.session_id, s.filename
                   FROM issues i JOIN review_sessions s ON s.id = i.session_id
                   WHERE i.id = ?""",
                (issue_id,),
            ).fetchone()
        return dict(row) if row else None

    # ── Dashboard / Statistics ────────────────────────────────────────────────

    def get_dashboard_stats(self) -> dict[str, Any]:
        with self._connect() as connection:
            total_reviews = connection.execute("SELECT COUNT(*) as c FROM review_sessions").fetchone()["c"]
            avg_score_row = connection.execute("SELECT AVG(score) as avg FROM review_sessions").fetchone()
            avg_score = round(avg_score_row["avg"]) if avg_score_row["avg"] else 0
            total_issues = connection.execute("SELECT COUNT(*) as c FROM issues").fetchone()["c"]
            open_issues = connection.execute("SELECT COUNT(*) as c FROM issues WHERE status='open'").fetchone()["c"]
            resolved_issues = connection.execute("SELECT COUNT(*) as c FROM issues WHERE status='resolved'").fetchone()["c"]
            sev_rows = connection.execute(
                "SELECT severity, COUNT(*) as cnt FROM issues GROUP BY severity"
            ).fetchall()
            cat_rows = connection.execute(
                "SELECT category, COUNT(*) as cnt FROM issues GROUP BY category ORDER BY cnt DESC LIMIT 5"
            ).fetchall()
            recent = connection.execute(
                "SELECT id, filename, profile_id, score, created_at FROM review_sessions ORDER BY created_at DESC LIMIT 5"
            ).fetchall()
            by_severity = {r["severity"]: r["cnt"] for r in sev_rows}
            return {
                "total_reviews": total_reviews,
                "average_score": avg_score,
                "total_issues": total_issues,
                "open_issues": open_issues,
                "resolved_issues": resolved_issues,
                "issues_by_severity": by_severity,
                "top_categories": [{r["category"]: r["cnt"]} for r in cat_rows],
                "recent_reviews": [dict(r) for r in recent],
            }

    def get_statistics(self) -> dict[str, Any]:
        with self._connect() as connection:
            # Count issues by category for percentage calculation
            total = connection.execute("SELECT COUNT(*) as c FROM issues").fetchone()["c"] or 1
            cat_rows = connection.execute(
                "SELECT category, COUNT(*) as cnt FROM issues GROUP BY category"
            ).fetchall()
            # Score trend: last 10 sessions
            trend_rows = connection.execute(
                "SELECT created_at, score FROM review_sessions ORDER BY created_at DESC LIMIT 10"
            ).fetchall()
            stats = {
                "total_issues": total,
                "categories": {},
                "trend": [dict(r) for r in reversed(trend_rows)],
            }
            for r in cat_rows:
                stats["categories"][r["category"]] = round(r["cnt"] / total * 100, 1)
            return stats

    # ── History Compare ───────────────────────────────────────────────────────

    def compare_sessions(self, session_id_1: str, session_id_2: str) -> dict[str, Any]:
        s1 = self.get_session(session_id_1)
        s2 = self.get_session(session_id_2)
        if not s1 or not s2:
            return {"error": "One or both sessions not found"}
        i1, _ = self.list_issues(session_id=session_id_1, limit=500)
        i2, _ = self.list_issues(session_id=session_id_2, limit=500)
        def count_sev(issues):
            h=sum(1 for i in issues if i["severity"]=="high"); m=sum(1 for i in issues if i["severity"]=="medium"); l=sum(1 for i in issues if i["severity"]=="low")
            return {"high":h,"medium":m,"low":l}
        sev1, sev2 = count_sev(i1), count_sev(i2)
        # Find common issue_id patterns
        ids1 = {i["issue_id"] for i in i1}
        ids2 = {i["issue_id"] for i in i2}
        improved = ids1 - ids2
        new_in_s2 = ids2 - ids1
        remaining = ids1 & ids2
        return {
            "session_1": {"id": session_id_1, "score": s1["score"], "date": s1.get("created_at"), "issues": len(i1), "by_severity": sev1},
            "session_2": {"id": session_id_2, "score": s2["score"], "date": s2.get("created_at"), "issues": len(i2), "by_severity": sev2},
            "score_change": s2["score"] - s1["score"],
            "issue_change": len(i2) - len(i1),
            "improved_issues": list(improved)[:20],
            "new_issues": list(new_in_s2)[:20],
            "remaining_issues": list(remaining)[:20],
            "severity_change": {"high": sev2["high"]-sev1["high"], "medium": sev2["medium"]-sev1["medium"], "low": sev2["low"]-sev1["low"]},
        }

    # ── Search ────────────────────────────────────────────────────────────────

    def search_all(self, query: str, limit: int = 20) -> dict[str, list[dict[str, Any]]]:
        like = f"%{query}%"
        docs = []
        sessions = []
        issues = []
        with self._connect() as connection:
            docs_rows = connection.execute(
                "SELECT id, original_name, content_type, size, created_at FROM documents WHERE original_name LIKE ? LIMIT ?",
                (like, limit),
            ).fetchall()
            docs = [dict(r) for r in docs_rows]
            sess_rows = connection.execute(
                "SELECT id, filename, profile_id, score, status, created_at FROM review_sessions WHERE filename LIKE ? OR summary LIKE ? LIMIT ?",
                (like, like, limit),
            ).fetchall()
            sessions = [dict(r) for r in sess_rows]
            issue_rows = connection.execute(
                "SELECT id, issue_id, message, severity, category, status FROM issues WHERE message LIKE ? OR recommendation LIKE ? LIMIT ?",
                (like, like, limit),
            ).fetchall()
            issues = [dict(r) for r in issue_rows]
        return {"documents": docs, "sessions": sessions, "issues": issues}

    # ── Packs ─────────────────────────────────────────────────────────────────

    def list_packs(self) -> list[dict[str, Any]]:
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

    def get_packs_for_profile(self, profile_id: str) -> list[dict[str, Any]]:
        return [p for p in self.list_packs() if p.get("profile") == profile_id]

    # ── Autofix Actions ───────────────────────────────────────────────────────

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
    ) -> str:
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
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM autofix_actions
                   WHERE session_id = ? AND action_type = 'apply' AND reverted_at IS NULL
                   ORDER BY applied_at DESC""",
                (session_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def revert_autofix_action(self, action_id: str, reverted_document: str = "") -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE autofix_actions
                   SET action_type = 'revert', reverted_at = datetime('now'),
                       reverted_document = ?
                   WHERE id = ?""",
                (reverted_document, action_id),
            )
            return cursor.rowcount > 0

    def get_autofix_history(self, session_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM autofix_actions
                   WHERE session_id = ?
                   ORDER BY applied_at DESC""",
                (session_id,),
            ).fetchall()
        return [dict(r) for r in rows]
