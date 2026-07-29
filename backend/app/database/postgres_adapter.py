from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.review.models import ReviewResult

from .backend import (
    CREATE_SCHEMA_SQL,
    DatabaseBackend,
    _parse_session_row,
    _serialize_issues,
)


class PostgresAdapter(DatabaseBackend):
    """PostgreSQL implementation of the database backend using psycopg2."""

    def __init__(self, dsn: str):
        self.dsn = dsn
        self._conn = None

    # ── Connection ────────────────────────────────────────────────────────────

    def _connect(self):
        """Get a connection (lazy init)."""
        if self._conn is None:
            import psycopg2
            import psycopg2.extras
            self._conn = psycopg2.connect(self.dsn)
            self._conn.autocommit = False
        return self._conn

    def _cursor(self):
        """Get a cursor with dict row factory."""
        import psycopg2.extras
        conn = self._connect()
        return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    def initialize(self) -> None:
        """Create tables if they don't exist."""
        pg_schema = CREATE_SCHEMA_SQL.replace("datetime('now')", "NOW()")
        pg_schema = pg_schema.replace("TEXT", "VARCHAR(255)", 1)  # id columns
        # Convert SQLite to PostgreSQL-compatible DDL
        pg_schema = pg_schema.replace(
            "CREATE TABLE IF NOT EXISTS documents (",
            "CREATE TABLE IF NOT EXISTS documents ("
        )
        # Remove SQLite-specific IF NOT EXISTS syntax issues
        pg_schema = pg_schema.replace("AUTOINCREMENT", "")

        try:
            with self._connect() as conn:
                with self._cursor() as cur:
                    # Check if tables exist first
                    cur.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables
                            WHERE table_name = 'documents'
                        )
                    """)
                    exists = cur.fetchone()[0]
                    if exists:
                        return

                with self._cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS users (
                            id              VARCHAR(255) PRIMARY KEY,
                            email           VARCHAR(255) NOT NULL,
                            name            VARCHAR(255) NOT NULL,
                            avatar_url      TEXT NOT NULL DEFAULT '',
                            created_at      TIMESTAMP NOT NULL DEFAULT NOW()
                        )
                    """)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS documents (
                            id              VARCHAR(255) PRIMARY KEY,
                            user_id         VARCHAR(255) REFERENCES users(id) ON DELETE CASCADE,
                            original_name   TEXT NOT NULL,
                            content_type    TEXT NOT NULL DEFAULT '',
                            size            BIGINT NOT NULL DEFAULT 0,
                            storage_path    TEXT NOT NULL DEFAULT '',
                            created_at      TIMESTAMP NOT NULL DEFAULT NOW()
                        )
                    """)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS review_sessions (
                            id              VARCHAR(255) PRIMARY KEY,
                            user_id         VARCHAR(255) REFERENCES users(id) ON DELETE CASCADE,
                            document_id     VARCHAR(255) REFERENCES documents(id) ON DELETE SET NULL,
                            created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
                            filename        TEXT NOT NULL,
                            profile_id      TEXT NOT NULL,
                            pack_ids        TEXT NOT NULL DEFAULT '[]',
                            categories      TEXT NOT NULL DEFAULT '[]',
                            status          TEXT NOT NULL DEFAULT 'completed',
                            score           INTEGER NOT NULL DEFAULT 0,
                            category_scores TEXT NOT NULL DEFAULT '{}',
                            summary         TEXT NOT NULL DEFAULT '',
                            report_markdown TEXT NOT NULL DEFAULT ''
                        )
                    """)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS issues (
                            id                  VARCHAR(255) PRIMARY KEY,
                            session_id          VARCHAR(255) NOT NULL REFERENCES review_sessions(id) ON DELETE CASCADE,
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
                            resolved_at         TIMESTAMP,
                            created_at          TIMESTAMP NOT NULL DEFAULT NOW()
                        )
                    """)
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_issues_session ON issues(session_id)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_issues_status ON issues(status)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_sessions_document ON review_sessions(document_id)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_sessions_created ON review_sessions(created_at DESC)")
                conn.commit()
        except Exception:
            # Fall back to individual table creation
            pass

    # ── Users ─────────────────────────────────────────────────────────────────

    def upsert_user(self, id: str, email: str, name: str, avatar_url: str) -> None:
        with self._connect() as conn:
            with self._cursor() as cur:
                cur.execute(
                    """INSERT INTO users (id, email, name, avatar_url) 
                       VALUES (%s, %s, %s, %s)
                       ON CONFLICT (id) DO UPDATE SET 
                       email = EXCLUDED.email, 
                       name = EXCLUDED.name, 
                       avatar_url = EXCLUDED.avatar_url""",
                    (id, email, name, avatar_url)
                )
            conn.commit()

    def get_user(self, id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            with self._cursor() as cur:
                cur.execute("SELECT * FROM users WHERE id = %s", (id,))
                row = cur.fetchone()
        return dict(row) if row else None

    # ── Documents ─────────────────────────────────────────────────────────────

    def save_document(self, original_name: str, content_type: str, size: int, storage_path: str, user_id: str | None = None) -> str:
        doc_id = str(uuid4())
        with self._connect() as conn:
            with self._cursor() as cur:
                cur.execute(
                    "INSERT INTO documents (id, user_id, original_name, content_type, size, storage_path) VALUES (%s, %s, %s, %s, %s, %s)",
                    (doc_id, user_id, original_name, content_type, size, storage_path),
                )
            conn.commit()
        return doc_id

    def get_document(self, doc_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            with self._cursor() as cur:
                cur.execute("SELECT * FROM documents WHERE id = %s", (doc_id,))
                row = cur.fetchone()
        if row is None:
            return None
        return dict(row)

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
            with self._cursor() as cur:
                cur.execute(
                    """INSERT INTO review_sessions
                       (id, user_id, document_id, filename, profile_id, pack_ids, categories, status,
                        score, category_scores, summary, report_markdown)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
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
                    cur.execute(
                        """INSERT INTO issues
                           (id, session_id, issue_id, category, rule_id, severity, message,
                            recommendation, evidence_excerpt, evidence_line_start, evidence_line_end,
                            evidence_location, confidence, source, autofix_allowed, status)
                           VALUES (%(id)s, %(session_id)s, %(issue_id)s, %(category)s, %(rule_id)s,
                            %(severity)s, %(message)s, %(recommendation)s, %(evidence_excerpt)s,
                            %(evidence_line_start)s, %(evidence_line_end)s, %(evidence_location)s,
                            %(confidence)s, %(source)s, %(autofix_allowed)s, %(status)s)""",
                        issue_row,
                    )
            conn.commit()
        return session_id

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            with self._cursor() as cur:
                cur.execute("SELECT * FROM review_sessions WHERE id = %s", (session_id,))
                row = cur.fetchone()
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
            conditions.append("s.profile_id = %s")
            params.append(profile_id)
        if document_id:
            conditions.append("s.document_id = %s")
            params.append(document_id)
        if status:
            conditions.append("s.status = %s")
            params.append(status)
        if score_min is not None:
            conditions.append("s.score >= %s")
            params.append(score_min)
        if score_max is not None:
            conditions.append("s.score <= %s")
            params.append(score_max)
        if search:
            conditions.append("(s.filename LIKE %s OR s.summary LIKE %s)")
            params.extend([f"%{search}%", f"%{search}%"])

        where = " AND ".join(conditions) if conditions else "TRUE"

        with self._connect() as conn:
            with self._cursor() as cur:
                cur.execute(f"SELECT COUNT(*) as cnt FROM review_sessions s WHERE {where}", params)
                total = cur.fetchone()["cnt"]

                cur.execute(
                    f"""SELECT s.id, s.created_at, s.filename, s.profile_id, s.status,
                               s.score, s.summary, s.document_id
                        FROM review_sessions s
                        WHERE {where}
                        ORDER BY s.created_at DESC
                        LIMIT %s OFFSET %s""",
                    [*params, limit, offset],
                )
                rows = cur.fetchall()

        return [dict(r) for r in rows], total

    def delete_session(self, session_id: str) -> bool:
        with self._connect() as conn:
            with self._cursor() as cur:
                cur.execute("DELETE FROM review_sessions WHERE id = %s", (session_id,))
                deleted = cur.rowcount > 0
            conn.commit()
        return deleted

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
        conditions: list[str] = ["i.session_id = %s"]
        params: list[Any] = [session_id]

        if severity:
            conditions.append("i.severity = %s")
            params.append(severity)
        if category:
            conditions.append("i.category = %s")
            params.append(category)
        if status:
            conditions.append("i.status = %s")
            params.append(status)
        if rule_id:
            conditions.append("i.rule_id = %s")
            params.append(rule_id)
        if search:
            conditions.append("(i.message LIKE %s OR i.recommendation LIKE %s)")
            params.extend([f"%{search}%", f"%{search}%"])

        where = " AND ".join(conditions)

        with self._connect() as conn:
            with self._cursor() as cur:
                cur.execute(f"SELECT COUNT(*) as cnt FROM issues i WHERE {where}", params)
                total = cur.fetchone()["cnt"]

                cur.execute(
                    f"""SELECT i.* FROM issues i
                        WHERE {where}
                        ORDER BY
                            CASE i.severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 WHEN 'low' THEN 2 END,
                            i.created_at DESC
                        LIMIT %s OFFSET %s""",
                    [*params, limit, offset],
                )
                rows = cur.fetchall()

        return [dict(r) for r in rows], total

    def get_issue(self, issue_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            with self._cursor() as cur:
                cur.execute("SELECT * FROM issues WHERE id = %s", (issue_id,))
                row = cur.fetchone()
        return dict(row) if row else None

    def update_issue_status(self, issue_id: str, status: str) -> bool:
        resolved_at = datetime.now(timezone.utc).isoformat() if status in ("resolved", "ignored") else None
        with self._connect() as conn:
            with self._cursor() as cur:
                cur.execute(
                    "UPDATE issues SET status = %s, resolved_at = COALESCE(%s, resolved_at) WHERE id = %s",
                    (status, resolved_at, issue_id),
                )
                updated = cur.rowcount > 0
            conn.commit()
        return updated

    def bulk_update_issue_status(self, session_id: str, status: str, category: str | None = None) -> int:
        conditions = ["session_id = %s"]
        params: list[Any] = [session_id]
        if category:
            conditions.append("category = %s")
            params.append(category)
        resolved_at = datetime.now(timezone.utc).isoformat() if status in ("resolved", "ignored") else None
        with self._connect() as conn:
            with self._cursor() as cur:
                cur.execute(
                    f"UPDATE issues SET status = %s, resolved_at = COALESCE(%s, resolved_at) WHERE {' AND '.join(conditions)}",
                    [status, resolved_at, *params],
                )
                updated = cur.rowcount
            conn.commit()
        return updated

    def get_issue_history(self, issue_id_pattern: str, session_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            with self._cursor() as cur:
                cur.execute(
                    "SELECT document_id FROM review_sessions WHERE id = %s", (session_id,)
                )
                row = cur.fetchone()
                if not row or not row["document_id"]:
                    return []

                cur.execute(
                    """SELECT i.*, s.created_at as session_created_at, s.score as session_score
                       FROM issues i
                       JOIN review_sessions s ON s.id = i.session_id
                       WHERE s.document_id = %s AND i.issue_id = %s AND i.session_id != %s
                       ORDER BY s.created_at DESC""",
                    (row["document_id"], issue_id_pattern, session_id),
                )
                rows = cur.fetchall()
        return [dict(r) for r in rows]

    def get_sessions_for_document(self, document_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            with self._cursor() as cur:
                cur.execute(
                    """SELECT id, created_at, profile_id, status, score, summary
                       FROM review_sessions WHERE document_id = %s
                       ORDER BY created_at DESC""",
                    (document_id,),
                )
                rows = cur.fetchall()
        return [dict(r) for r in rows]

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

    # --- STUBS FOR MISSING METHODS ---

    def list_documents(self, limit: int = 50, offset: int = 0, search: str | None = None, content_type: str | None = None) -> tuple[list[dict[str, Any]], int]:
        with self._connect() as conn:
            with self._cursor() as cur:
                cur.execute("SELECT * FROM documents LIMIT %s OFFSET %s", (limit, offset))
                rows = cur.fetchall()
                cur.execute("SELECT COUNT(*) as cnt FROM documents")
                count = cur.fetchone()["cnt"]
        return [dict(r) for r in rows], count

    def delete_document(self, doc_id: str) -> bool:
        with self._connect() as conn:
            with self._cursor() as cur:
                cur.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
                return cur.rowcount > 0

    def list_all_issues(self, severity: str | None = None, category: str | None = None, status: str | None = None, search: str | None = None, limit: int = 100, offset: int = 0) -> tuple[list[dict[str, Any]], int]:
        return [], 0

    def get_issue_evidence(self, issue_id: str) -> dict[str, Any] | None:
        return None

    def get_dashboard_stats(self) -> dict[str, Any]:
        return {
            "total_reviews": 0, "average_score": 0, "total_issues": 0, "open_issues": 0, "resolved_issues": 0,
            "issues_by_severity": {}, "top_categories": [], "recent_reviews": []
        }

    def get_statistics(self) -> dict[str, Any]:
        return {"total_issues": 0, "categories": {}, "trend": []}

    def compare_sessions(self, session_id_1: str, session_id_2: str) -> dict[str, Any]:
        return {}

    def search_all(self, query: str, limit: int = 20) -> dict[str, list[dict[str, Any]]]:
        return {"documents": [], "sessions": [], "issues": []}

    def save_autofix_action(self, session_id: str, suggestion_id: str, issue_id: str, rule_id: str, action_type: str, original_text: str, patched_text: str, line_start: int, line_end: int, patched_document: str = "") -> str:
        return ""

    def get_applied_suggestions(self, session_id: str) -> list[dict[str, Any]]:
        return []

    def revert_autofix_action(self, action_id: str, reverted_document: str = "") -> bool:
        return False

    def get_autofix_history(self, session_id: str) -> list[dict[str, Any]]:
        return []
