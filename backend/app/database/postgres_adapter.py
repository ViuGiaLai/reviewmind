from __future__ import annotations

import json
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

import psycopg2
import psycopg2.extras
try:
    from psycopg2 import pool as pg_pool
except ImportError:  # Minimal test doubles / stripped psycopg2 builds.
    pg_pool = None

from app.review.models import ReviewResult
from app.operations import metrics

from .backend import (
    CREATE_SCHEMA_SQL,
    DatabaseBackend,
    _parse_session_row,
    _serialize_issues,
)



class _DirectConnectionPool:
    """Compatibility fallback; production psycopg2 provides ThreadedConnectionPool."""
    def __init__(self, minconn: int, maxconn: int, dsn: str, **kwargs):
        self.dsn = dsn
    def getconn(self):
        return psycopg2.connect(self.dsn)
    def putconn(self, conn, close: bool = False):
        conn.close()
    def closeall(self):
        return None
class PostgresAdapter(DatabaseBackend):
    """PostgreSQL implementation of the database backend using psycopg2."""

    def __init__(
        self, dsn: str, min_pool_size: int = 1, max_pool_size: int = 10,
        statement_timeout_ms: int = 30000,
    ):
        self.dsn = dsn
        self.min_pool_size = max(1, min_pool_size)
        self.max_pool_size = max(self.min_pool_size, max_pool_size)
        self.statement_timeout_ms = max(1000, statement_timeout_ms)
        self._pool: Any = None
        self._pool_lock = threading.Lock()

    def _ensure_pool(self) -> Any:
        if self._pool is None:
            with self._pool_lock:
                if self._pool is None:
                    pool_class = pg_pool.ThreadedConnectionPool if pg_pool else _DirectConnectionPool
                    self._pool = pool_class(
                        self.min_pool_size, self.max_pool_size, self.dsn,
                    )
        return self._pool

    @contextmanager
    def _connect(self) -> Iterator[psycopg2.extensions.connection]:
        """Borrow a transaction-safe connection from the process-local pool."""
        pool = self._ensure_pool()
        started = time.perf_counter()
        conn = None
        try:
            conn = pool.getconn()
            metrics.observe(
                "reviewmind_db_pool_wait_seconds",
                time.perf_counter() - started,
            )
            if conn.closed:
                pool.putconn(conn, close=True)
                conn = pool.getconn()
            conn.autocommit = False
            # Neon and PgBouncer poolers reject statement_timeout in startup options.
            # SET LOCAL applies the guardrail to this borrowed transaction only.
            with conn.cursor() as timeout_cursor:
                timeout_cursor.execute(f"SET LOCAL statement_timeout = {self.statement_timeout_ms}")
            yield conn
        except (pg_pool.PoolError if pg_pool else RuntimeError):
            metrics.increment("reviewmind_db_pool_exhausted_total")
            raise
        except Exception:
            if conn is not None and not conn.closed:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise
        finally:
            if conn is not None:
                is_closed = bool(conn.closed)
                if not is_closed:
                    try:
                        # Read-only methods otherwise return an open transaction to the pool.
                        conn.rollback()
                    except Exception:
                        is_closed = True
                try:
                    pool.putconn(conn, close=is_closed)
                except Exception:
                    pass

    def close(self) -> None:
        """Close all pooled connections during application shutdown/tests."""
        with self._pool_lock:
            if self._pool is not None:
                self._pool.closeall()
                self._pool = None
    def _cursor(self, conn):
        """Get a cursor with dict row factory from an existing connection."""
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
                # Run idempotent DDL on every startup. Returning when one legacy
                # table existed prevented newer tables from ever being migrated.
                with self._cursor(conn) as cur:
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
                        CREATE TABLE IF NOT EXISTS reference_templates (
                            id              VARCHAR(255) PRIMARY KEY,
                            user_id         VARCHAR(255) REFERENCES users(id) ON DELETE CASCADE,
                            original_name   TEXT NOT NULL,
                            size            BIGINT NOT NULL DEFAULT 0,
                            storage_path    TEXT NOT NULL DEFAULT '',
                            analysis        TEXT NOT NULL DEFAULT '{}',
                            created_at      TIMESTAMP NOT NULL DEFAULT NOW()
                        )
                    """)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS evaluation_profiles (
                            id                    VARCHAR(255) PRIMARY KEY,
                            user_id               VARCHAR(255) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                            name                  TEXT NOT NULL,
                            description           TEXT NOT NULL DEFAULT '',
                            base_profile_id       TEXT NOT NULL DEFAULT 'academic',
                            document_types        TEXT NOT NULL DEFAULT '[]',
                            knowledge_pack_ids    TEXT NOT NULL DEFAULT '[]',
                            reference_template_id VARCHAR(255) REFERENCES reference_templates(id) ON DELETE SET NULL,
                            enabled_categories    TEXT NOT NULL DEFAULT '[]',
                            ai_review_enabled     BOOLEAN NOT NULL DEFAULT TRUE,
                            auto_fix_enabled      BOOLEAN NOT NULL DEFAULT FALSE,
                            scoring_profile       TEXT NOT NULL DEFAULT 'standard',
                            language              TEXT NOT NULL DEFAULT 'vi',
                            review_mode           TEXT NOT NULL DEFAULT 'standard',
                            visibility            TEXT NOT NULL DEFAULT 'private',
                            created_at            TIMESTAMP NOT NULL DEFAULT NOW(),
                            updated_at            TIMESTAMP NOT NULL DEFAULT NOW()
                        )
                    """)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS review_sessions (
                            id              VARCHAR(255) PRIMARY KEY,
                            user_id         VARCHAR(255) REFERENCES users(id) ON DELETE CASCADE,
                            document_id     VARCHAR(255) REFERENCES documents(id) ON DELETE SET NULL,
                            reference_template_id VARCHAR(255) REFERENCES reference_templates(id) ON DELETE SET NULL,
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
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS autofix_actions (
                            id                VARCHAR(255) PRIMARY KEY,
                            session_id        VARCHAR(255) NOT NULL REFERENCES review_sessions(id) ON DELETE CASCADE,
                            suggestion_id     TEXT NOT NULL,
                            issue_id          TEXT NOT NULL DEFAULT '',
                            rule_id           TEXT NOT NULL DEFAULT '',
                            action_type       TEXT NOT NULL DEFAULT 'apply',
                            original_text     TEXT NOT NULL DEFAULT '',
                            patched_text      TEXT NOT NULL DEFAULT '',
                            line_start        INTEGER NOT NULL DEFAULT 0,
                            line_end          INTEGER NOT NULL DEFAULT 0,
                            applied_at        TIMESTAMP NOT NULL DEFAULT NOW(),
                            reverted_at       TIMESTAMP,
                            reverted_document TEXT NOT NULL DEFAULT '',
                            patched_document  TEXT NOT NULL DEFAULT ''
                        )
                    """)
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_autofix_session ON autofix_actions(session_id)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_autofix_suggestion ON autofix_actions(suggestion_id)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_issues_session ON issues(session_id)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_issues_status ON issues(status)")
                    cur.execute("ALTER TABLE review_sessions ADD COLUMN IF NOT EXISTS reference_template_id VARCHAR(255) REFERENCES reference_templates(id) ON DELETE SET NULL")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_sessions_document ON review_sessions(document_id)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_sessions_template ON review_sessions(reference_template_id)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_sessions_created ON review_sessions(created_at DESC)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_reference_templates_user ON reference_templates(user_id, created_at DESC)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_evaluation_profiles_user ON evaluation_profiles(user_id, updated_at DESC)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_documents_user_created ON documents(user_id, created_at DESC)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_created ON review_sessions(user_id, created_at DESC)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_profile_created ON review_sessions(user_id, profile_id, created_at DESC)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_issues_session_status_severity ON issues(session_id, status, severity)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_issues_session_rule ON issues(session_id, rule_id)")
                conn.commit()
        except Exception:
            # Startup must fail visibly when schema migration cannot complete.
            # Continuing would make authenticated APIs fail later with missing tables.
            raise

    # ── Users ─────────────────────────────────────────────────────────────────

    def upsert_user(self, id: str, email: str, name: str, avatar_url: str) -> None:
        with self._connect() as conn:
            with self._cursor(conn) as cur:
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
            with self._cursor(conn) as cur:
                cur.execute("SELECT * FROM users WHERE id = %s", (id,))
                row = cur.fetchone()
        return dict(row) if row else None

    # ── Documents ─────────────────────────────────────────────────────────────

    def save_document(self, original_name: str, content_type: str, size: int, storage_path: str, user_id: str | None = None) -> str:
        doc_id = str(uuid4())
        with self._connect() as conn:
            with self._cursor(conn) as cur:
                cur.execute(
                    "INSERT INTO documents (id, user_id, original_name, content_type, size, storage_path) VALUES (%s, %s, %s, %s, %s, %s)",
                    (doc_id, user_id, original_name, content_type, size, storage_path),
                )
            conn.commit()
        return doc_id

    def get_document(self, doc_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            with self._cursor(conn) as cur:
                cur.execute("SELECT * FROM documents WHERE id = %s", (doc_id,))
                row = cur.fetchone()
        if row is None:
            return None
        return dict(row)

    # ── Review Sessions ───────────────────────────────────────────────────────

    def save_reference_template(
        self, original_name: str, size: int, storage_path: str,
        analysis: dict[str, Any], user_id: str | None = None,
    ) -> str:
        template_id = str(uuid4())
        with self._connect() as conn:
            with self._cursor(conn) as cur:
                cur.execute(
                    """INSERT INTO reference_templates
                       (id, user_id, original_name, size, storage_path, analysis)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (template_id, user_id, original_name, size, storage_path,
                     json.dumps(analysis, ensure_ascii=False)),
                )
            conn.commit()
        return template_id

    def get_reference_template(self, template_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            with self._cursor(conn) as cur:
                cur.execute("SELECT * FROM reference_templates WHERE id = %s", (template_id,))
                row = cur.fetchone()
        if not row:
            return None
        data = dict(row)
        if isinstance(data.get("analysis"), str):
            data["analysis"] = json.loads(data["analysis"])
        return data

    def list_reference_templates(self, user_id: str | None = None) -> list[dict[str, Any]]:
        with self._connect() as conn:
            with self._cursor(conn) as cur:
                if user_id is None:
                    cur.execute("SELECT * FROM reference_templates ORDER BY created_at DESC")
                else:
                    cur.execute(
                        "SELECT * FROM reference_templates WHERE user_id = %s ORDER BY created_at DESC",
                        (user_id,),
                    )
                rows = cur.fetchall()
        result = []
        for row in rows:
            data = dict(row)
            if isinstance(data.get("analysis"), str):
                data["analysis"] = json.loads(data["analysis"])
            result.append(data)
        return result

    def delete_reference_template(self, template_id: str) -> bool:
        with self._connect() as conn:
            with self._cursor(conn) as cur:
                cur.execute("DELETE FROM reference_templates WHERE id = %s", (template_id,))
                deleted = cur.rowcount > 0
            conn.commit()
        return deleted

    @staticmethod
    def _parse_evaluation_profile(row: Any) -> dict[str, Any]:
        data = dict(row)
        for key in ("document_types", "knowledge_pack_ids", "enabled_categories"):
            if isinstance(data.get(key), str):
                data[key] = json.loads(data[key])
        data["ai_review_enabled"] = bool(data.get("ai_review_enabled"))
        data["auto_fix_enabled"] = bool(data.get("auto_fix_enabled"))
        return data

    def create_evaluation_profile(self, user_id: str, data: dict[str, Any]) -> str:
        profile_id = str(uuid4())
        with self._connect() as conn:
            with self._cursor(conn) as cur:
                cur.execute(
                    """INSERT INTO evaluation_profiles
                       (id, user_id, name, description, base_profile_id, document_types,
                        knowledge_pack_ids, reference_template_id, enabled_categories,
                        ai_review_enabled, auto_fix_enabled, scoring_profile, language,
                        review_mode, visibility)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        profile_id, user_id, data["name"], data.get("description", ""),
                        data.get("base_profile_id", "academic"),
                        json.dumps(data.get("document_types", []), ensure_ascii=False),
                        json.dumps(data.get("knowledge_pack_ids", []), ensure_ascii=False),
                        data.get("reference_template_id"),
                        json.dumps(data.get("enabled_categories", []), ensure_ascii=False),
                        data.get("ai_review_enabled", True), data.get("auto_fix_enabled", False),
                        data.get("scoring_profile", "standard"), data.get("language", "vi"),
                        data.get("review_mode", "standard"), data.get("visibility", "private"),
                    ),
                )
            conn.commit()
        return profile_id

    def get_evaluation_profile(self, profile_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            with self._cursor(conn) as cur:
                cur.execute("SELECT * FROM evaluation_profiles WHERE id = %s", (profile_id,))
                row = cur.fetchone()
        return self._parse_evaluation_profile(row) if row else None

    def list_evaluation_profiles(self, user_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            with self._cursor(conn) as cur:
                cur.execute(
                    """SELECT p.*, t.original_name AS template_name
                       FROM evaluation_profiles p
                       LEFT JOIN reference_templates t ON t.id = p.reference_template_id
                       WHERE p.user_id = %s ORDER BY p.updated_at DESC""",
                    (user_id,),
                )
                rows = cur.fetchall()
        return [self._parse_evaluation_profile(row) for row in rows]

    def update_evaluation_profile(
        self, profile_id: str, user_id: str, data: dict[str, Any]
    ) -> bool:
        with self._connect() as conn:
            with self._cursor(conn) as cur:
                cur.execute(
                    """UPDATE evaluation_profiles SET
                       name = %s, description = %s, base_profile_id = %s,
                       document_types = %s, knowledge_pack_ids = %s,
                       reference_template_id = %s, enabled_categories = %s,
                       ai_review_enabled = %s, auto_fix_enabled = %s,
                       scoring_profile = %s, language = %s, review_mode = %s,
                       visibility = %s, updated_at = NOW()
                       WHERE id = %s AND user_id = %s""",
                    (
                        data["name"], data.get("description", ""),
                        data.get("base_profile_id", "academic"),
                        json.dumps(data.get("document_types", []), ensure_ascii=False),
                        json.dumps(data.get("knowledge_pack_ids", []), ensure_ascii=False),
                        data.get("reference_template_id"),
                        json.dumps(data.get("enabled_categories", []), ensure_ascii=False),
                        data.get("ai_review_enabled", True), data.get("auto_fix_enabled", False),
                        data.get("scoring_profile", "standard"), data.get("language", "vi"),
                        data.get("review_mode", "standard"), data.get("visibility", "private"),
                        profile_id, user_id,
                    ),
                )
                updated = cur.rowcount > 0
            conn.commit()
        return updated

    def delete_evaluation_profile(self, profile_id: str, user_id: str) -> bool:
        with self._connect() as conn:
            with self._cursor(conn) as cur:
                cur.execute(
                    "DELETE FROM evaluation_profiles WHERE id = %s AND user_id = %s",
                    (profile_id, user_id),
                )
                deleted = cur.rowcount > 0
            conn.commit()
        return deleted

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
    ) -> str:
        session_id = str(uuid4())
        with self._connect() as conn:
            with self._cursor(conn) as cur:
                cur.execute(
                    """INSERT INTO review_sessions
                       (id, user_id, document_id, reference_template_id, filename, profile_id, pack_ids, categories, status,
                        score, category_scores, summary, report_markdown)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        session_id, user_id, document_id, reference_template_id, filename, profile_id,
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
            with self._cursor(conn) as cur:
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
        user_id: str | None = None,
        limit: int = 30,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        conditions: list[str] = []
        params: list[Any] = []

        if user_id is not None:
            conditions.append("s.user_id = %s")
            params.append(user_id)
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
            conditions.append("(s.filename ILIKE %s OR s.summary ILIKE %s)")
            params.extend([f"%{search}%", f"%{search}%"])

        where = " AND ".join(conditions) if conditions else "TRUE"

        with self._connect() as conn:
            with self._cursor(conn) as cur:
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
            with self._cursor(conn) as cur:
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
            conditions.append("(i.message ILIKE %s OR i.recommendation ILIKE %s)")
            params.extend([f"%{search}%", f"%{search}%"])

        where = " AND ".join(conditions)

        with self._connect() as conn:
            with self._cursor(conn) as cur:
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
            with self._cursor(conn) as cur:
                cur.execute("SELECT * FROM issues WHERE id = %s", (issue_id,))
                row = cur.fetchone()
        return dict(row) if row else None

    def update_issue_status(self, issue_id: str, status: str) -> bool:
        resolved_at = datetime.now(timezone.utc).isoformat() if status in ("resolved", "ignored") else None
        with self._connect() as conn:
            with self._cursor(conn) as cur:
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
            with self._cursor(conn) as cur:
                cur.execute(
                    f"UPDATE issues SET status = %s, resolved_at = COALESCE(%s, resolved_at) WHERE {' AND '.join(conditions)}",
                    [status, resolved_at, *params],
                )
                updated = cur.rowcount
            conn.commit()
        return updated

    def get_issue_history(
        self, issue_id_pattern: str, session_id: str, user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            with self._cursor(conn) as cur:
                cur.execute(
                    "SELECT document_id FROM review_sessions WHERE id = %s", (session_id,)
                )
                row = cur.fetchone()
                if not row or not row["document_id"]:
                    return []

                ownership_sql = " AND s.user_id = %s" if user_id is not None else ""
                params: list[Any] = [row["document_id"], issue_id_pattern, session_id]
                if user_id is not None:
                    params.append(user_id)
                cur.execute(
                    f"""SELECT i.*, s.created_at as session_created_at, s.score as session_score
                        FROM issues i
                        JOIN review_sessions s ON s.id = i.session_id
                        WHERE s.document_id = %s AND i.issue_id = %s AND i.session_id != %s
                        {ownership_sql}
                        ORDER BY s.created_at DESC""",
                    params,
                )
                rows = cur.fetchall()
        return [dict(r) for r in rows]

    def get_sessions_for_document(self, document_id: str, user_id: str | None = None) -> list[dict[str, Any]]:
        conditions = ["document_id = %s"]
        params: list[Any] = [document_id]
        if user_id is not None:
            conditions.append("user_id = %s")
            params.append(user_id)
        where = " AND ".join(conditions)
        with self._connect() as conn:
            with self._cursor(conn) as cur:
                cur.execute(
                    f"""SELECT id, created_at, profile_id, status, score, summary
                        FROM review_sessions WHERE {where}
                        ORDER BY created_at DESC""",
                    params,
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
                        "version": data.get("version", "1.0.0"),
                        "author": data.get("author", "ReviewMind"),
                        "website": data.get("website", ""),
                        "categories": data.get("categories", []),
                        "required_packs": data.get("required_packs", []),
                        "incompatible_packs": data.get("incompatible_packs", []),
                        "capability_count": len(data.get("capabilities", [])),
                    })
                except Exception:
                    pass
        return results

    def get_packs_for_profile(self, profile_id: str) -> list[dict[str, Any]]:
        return [p for p in self.list_packs() if p.get("profile") == profile_id]

    # ── Global Issues ─────────────────────────────────────────────────────────

    def list_all_issues(
        self,
        severity: str | None = None,
        category: str | None = None,
        status: str | None = None,
        search: str | None = None,
        user_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        conditions: list[str] = []
        params: list[Any] = []
        if user_id is not None:
            conditions.append("s.user_id = %s")
            params.append(user_id)
        if severity:
            conditions.append("i.severity = %s"); params.append(severity)
        if category:
            conditions.append("i.category = %s"); params.append(category)
        if status:
            conditions.append("i.status = %s"); params.append(status)
        if search:
            conditions.append("(i.message ILIKE %s OR i.recommendation ILIKE %s)")
            params.extend([f"%{search}%", f"%{search}%"])
        where = " AND ".join(conditions) if conditions else "TRUE"
        with self._connect() as conn:
            with self._cursor(conn) as cur:
                cur.execute(f"SELECT COUNT(*) as cnt FROM issues i JOIN review_sessions s ON s.id = i.session_id WHERE {where}", params)
                count = cur.fetchone()["cnt"]
                cur.execute(
                    f"""SELECT i.*, s.filename as session_filename, s.profile_id
                       FROM issues i JOIN review_sessions s ON s.id = i.session_id
                       WHERE {where}
                       ORDER BY CASE i.severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                                i.created_at DESC LIMIT %s OFFSET %s""",
                    [*params, limit, offset],
                )
                rows = cur.fetchall()
        return [dict(r) for r in rows], count

    def get_issue_evidence(self, issue_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            with self._cursor(conn) as cur:
                cur.execute(
                    """SELECT i.id, i.evidence_excerpt, i.evidence_line_start, i.evidence_line_end,
                              i.evidence_location, i.session_id, s.filename
                       FROM issues i JOIN review_sessions s ON s.id = i.session_id
                       WHERE i.id = %s""",
                    (issue_id,),
                )
                row = cur.fetchone()
        return dict(row) if row else None

    # ── Documents (full implementation) ────────────────────────────────────────

    def list_documents(
        self,
        search: str | None = None,
        content_type: str | None = None,
        user_id: str | None = None,
        limit: int = 30,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        conditions: list[str] = []
        params: list[Any] = []
        if user_id is not None:
            conditions.append("user_id = %s")
            params.append(user_id)
        if search:
            conditions.append("(original_name ILIKE %s OR id ILIKE %s)")
            params.extend([f"%{search}%", f"%{search}%"])
        if content_type:
            conditions.append("content_type = %s")
            params.append(content_type)
        where = " AND ".join(conditions) if conditions else "TRUE"
        with self._connect() as conn:
            with self._cursor(conn) as cur:
                cur.execute(f"SELECT COUNT(*) as cnt FROM documents WHERE {where}", params)
                count = cur.fetchone()["cnt"]
                cur.execute(
                    f"SELECT * FROM documents WHERE {where} ORDER BY created_at DESC LIMIT %s OFFSET %s",
                    [*params, limit, offset],
                )
                rows = cur.fetchall()
        return [dict(r) for r in rows], count

    def delete_document(self, doc_id: str) -> bool:
        with self._connect() as conn:
            with self._cursor(conn) as cur:
                cur.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
                deleted = cur.rowcount > 0
            conn.commit()
        return deleted

    # ── Dashboard / Statistics ────────────────────────────────────────────────

    def get_dashboard_stats(self, user_id: str | None = None) -> dict[str, Any]:
        """Dashboard aggregation with five bounded queries instead of eight scans."""
        session_where = "WHERE user_id = %s" if user_id is not None else ""
        issue_where = "WHERE s.user_id = %s" if user_id is not None else ""
        params = (user_id,) if user_id is not None else ()
        with self._connect() as conn:
            with self._cursor(conn) as cur:
                cur.execute(
                    f"SELECT COUNT(*) AS total_reviews, COALESCE(AVG(score), 0) AS average_score FROM review_sessions {session_where}",
                    params,
                )
                session_summary = cur.fetchone() or {}
                cur.execute(
                    f"""SELECT COUNT(*) AS total_issues,
                               COUNT(*) FILTER (WHERE i.status = 'open') AS open_issues,
                               COUNT(*) FILTER (WHERE i.status = 'resolved') AS resolved_issues
                        FROM issues i JOIN review_sessions s ON s.id = i.session_id
                        {issue_where}""",
                    params,
                )
                issue_summary = cur.fetchone() or {}
                cur.execute(
                    f"""SELECT i.severity, COUNT(*) AS cnt
                        FROM issues i JOIN review_sessions s ON s.id = i.session_id
                        {issue_where} GROUP BY i.severity""",
                    params,
                )
                sev_rows = cur.fetchall()
                cur.execute(
                    f"""SELECT i.category, COUNT(*) AS cnt
                        FROM issues i JOIN review_sessions s ON s.id = i.session_id
                        {issue_where} GROUP BY i.category ORDER BY cnt DESC LIMIT 5""",
                    params,
                )
                cat_rows = cur.fetchall()
                cur.execute(
                    f"""SELECT id, filename, profile_id, score, created_at
                        FROM review_sessions {session_where}
                        ORDER BY created_at DESC LIMIT 5""",
                    params,
                )
                recent = cur.fetchall()

        return {
            "total_reviews": session_summary.get("total_reviews", 0),
            "average_score": round(session_summary.get("average_score") or 0),
            "total_issues": issue_summary.get("total_issues", 0),
            "open_issues": issue_summary.get("open_issues", 0),
            "resolved_issues": issue_summary.get("resolved_issues", 0),
            "issues_by_severity": {r["severity"]: r["cnt"] for r in sev_rows},
            "top_categories": [{r["category"]: r["cnt"]} for r in cat_rows],
            "recent_reviews": [dict(r) for r in recent],
        }
    def get_statistics(self, user_id: str | None = None) -> dict[str, Any]:
        with self._connect() as conn:
            with self._cursor(conn) as cur:
                if user_id is not None:
                    cur.execute(
                        "SELECT COUNT(*) as c FROM issues i JOIN review_sessions s ON s.id = i.session_id WHERE s.user_id = %s",
                        (user_id,),
                    )
                else:
                    cur.execute("SELECT COUNT(*) as c FROM issues")
                total = cur.fetchone()["c"] or 1

                if user_id is not None:
                    cur.execute(
                        "SELECT i.category, COUNT(*) as cnt FROM issues i JOIN review_sessions s ON s.id = i.session_id WHERE s.user_id = %s GROUP BY i.category",
                        (user_id,),
                    )
                else:
                    cur.execute("SELECT category, COUNT(*) as cnt FROM issues GROUP BY category")
                cat_rows = cur.fetchall()

                if user_id is not None:
                    cur.execute(
                        "SELECT created_at, score FROM review_sessions WHERE user_id = %s ORDER BY created_at DESC LIMIT 10",
                        (user_id,),
                    )
                else:
                    cur.execute("SELECT created_at, score FROM review_sessions ORDER BY created_at DESC LIMIT 10")
                trend_rows = cur.fetchall()

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
            h = sum(1 for i in issues if i["severity"] == "high")
            m = sum(1 for i in issues if i["severity"] == "medium")
            l = sum(1 for i in issues if i["severity"] == "low")
            return {"high": h, "medium": m, "low": l}

        sev1, sev2 = count_sev(i1), count_sev(i2)
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
            "severity_change": {"high": sev2["high"] - sev1["high"], "medium": sev2["medium"] - sev1["medium"], "low": sev2["low"] - sev1["low"]},
        }

    # ── Search ────────────────────────────────────────────────────────────────

    def search_all(self, query: str, limit: int = 20, user_id: str | None = None) -> dict[str, list[dict[str, Any]]]:
        like = f"%{query}%"
        docs = []
        sessions = []
        issues = []
        with self._connect() as conn:
            with self._cursor(conn) as cur:
                if user_id is not None:
                    cur.execute(
                        "SELECT id, original_name, content_type, size, created_at FROM documents WHERE original_name ILIKE %s AND user_id = %s LIMIT %s",
                        (like, user_id, limit),
                    )
                else:
                    cur.execute(
                        "SELECT id, original_name, content_type, size, created_at FROM documents WHERE original_name ILIKE %s LIMIT %s",
                        (like, limit),
                    )
                docs = [dict(r) for r in cur.fetchall()]

                if user_id is not None:
                    cur.execute(
                        "SELECT id, filename, profile_id, score, status, created_at FROM review_sessions WHERE (filename ILIKE %s OR summary ILIKE %s) AND user_id = %s LIMIT %s",
                        (like, like, user_id, limit),
                    )
                else:
                    cur.execute(
                        "SELECT id, filename, profile_id, score, status, created_at FROM review_sessions WHERE filename ILIKE %s OR summary ILIKE %s LIMIT %s",
                        (like, like, limit),
                    )
                sessions = [dict(r) for r in cur.fetchall()]

                if user_id is not None:
                    cur.execute(
                        "SELECT i.id, i.issue_id, i.message, i.severity, i.category, i.status FROM issues i JOIN review_sessions s ON s.id = i.session_id WHERE (i.message ILIKE %s OR i.recommendation ILIKE %s) AND s.user_id = %s LIMIT %s",
                        (like, like, user_id, limit),
                    )
                else:
                    cur.execute(
                        "SELECT id, issue_id, message, severity, category, status FROM issues WHERE message ILIKE %s OR recommendation ILIKE %s LIMIT %s",
                        (like, like, limit),
                    )
                issues = [dict(r) for r in cur.fetchall()]
        return {"documents": docs, "sessions": sessions, "issues": issues}

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
        with self._connect() as conn:
            with self._cursor(conn) as cur:
                cur.execute(
                    """INSERT INTO autofix_actions
                       (id, session_id, suggestion_id, issue_id, rule_id, action_type,
                        original_text, patched_text, line_start, line_end, patched_document)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (action_id, session_id, suggestion_id, issue_id, rule_id, action_type,
                     original_text, patched_text, line_start, line_end, patched_document),
                )
            conn.commit()
        return action_id

    def get_applied_suggestions(self, session_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            with self._cursor(conn) as cur:
                cur.execute(
                    """SELECT * FROM autofix_actions
                       WHERE session_id = %s AND action_type = 'apply' AND reverted_at IS NULL
                       ORDER BY applied_at DESC""",
                    (session_id,),
                )
                rows = cur.fetchall()
        return [dict(r) for r in rows]

    def revert_autofix_action(self, action_id: str, reverted_document: str = "") -> bool:
        with self._connect() as conn:
            with self._cursor(conn) as cur:
                cur.execute(
                    """UPDATE autofix_actions
                       SET action_type = 'revert', reverted_at = NOW(),
                           reverted_document = %s
                       WHERE id = %s""",
                    (reverted_document, action_id),
                )
                updated = cur.rowcount > 0
            conn.commit()
        return updated

    def get_autofix_history(self, session_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            with self._cursor(conn) as cur:
                cur.execute(
                    """SELECT * FROM autofix_actions
                       WHERE session_id = %s
                       ORDER BY applied_at DESC""",
                    (session_id,),
                )
                rows = cur.fetchall()
        return [dict(r) for r in rows]
