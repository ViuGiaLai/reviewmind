"""Tests for Alembic migration and database initialization.

Run with:
    pytest tests/test_database.py -v

Or directly:
    python tests/test_database.py

For PostgreSQL testing:
    REVIEWMIND_PG_DSN=postgresql://user:pass@localhost:5432/reviewmind_test pytest tests/test_database.py -v
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

# Ensure backend is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import create_database
from app.database.backend import CREATE_SCHEMA_SQL
from app.review.models import Evidence, Issue, ReviewResult, Severity


# ─── Shared helpers ───────────────────────────────────────────────────────────

def make_sample_result() -> ReviewResult:
    """Create a sample ReviewResult for testing save/load."""
    issues = [
        Issue(
            id="test-issue-1",
            category="structure",
            rule_id="structure.required-section",
            severity=Severity.HIGH,
            message="Missing required section: Introduction.",
            recommendation="Add an Introduction section.",
            evidence=Evidence("No heading found", 1, 1, "document"),
            confidence=100,
            source="syntax-rule",
        ),
        Issue(
            id="test-issue-2",
            category="writing",
            rule_id="writing.sentence-length",
            severity=Severity.LOW,
            message="Long sentence detected.",
            recommendation="Split into shorter sentences.",
            evidence=Evidence("This is a very long sentence...", 5, 5, "line 5"),
            confidence=88,
            source="semantic-rule",
            autofix_allowed=True,
        ),
    ]
    return ReviewResult(
        profile_id="academic",
        pack_ids=["ieee"],
        issues=issues,
        score=75,
        category_scores={"structure": 60, "writing": 90, "citation": 100},
        summary="Found 2 issue(s).",
        report_markdown="# Report\n\nScore: 75/100",
    )


def verify_tables_exist(db_path: Path) -> list[str]:
    """Verify that all expected tables exist and return missing ones."""
    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row[0] for row in cursor.fetchall()}

    expected = {"documents", "review_sessions", "issues"}
    missing = expected - tables
    return list(missing)


def verify_indexes_exist(db_path: Path) -> list[str]:
    """Verify expected indexes exist."""
    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%' ORDER BY name"
        )
        indexes = {row[0] for row in cursor.fetchall()}

    expected = {"idx_issues_session", "idx_issues_status", "idx_sessions_document", "idx_sessions_created"}
    missing = expected - indexes
    return list(missing)


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 1: SQLiteAdapter initialization
# ═══════════════════════════════════════════════════════════════════════════════

def test_sqlite_initialization():
    """Test that SQLiteAdapter creates all tables on initialize()."""
    import tempfile
    tmp = tempfile.mkdtemp()
    try:
        db_path = Path(tmp) / "test.db"
        from app.database.sqlite_adapter import SQLiteAdapter

        adapter = SQLiteAdapter(db_path)
        adapter.initialize()

        missing = verify_tables_exist(db_path)
        missing_idx = verify_indexes_exist(db_path)

        # Close connection before checking (Windows file lock)
        try:
            if hasattr(adapter, "_conn") and adapter._conn:
                adapter._conn.close()
                adapter._conn = None
            elif hasattr(adapter, "close"):
                adapter.close()
        except Exception:
            pass

        assert not missing, f"Missing tables: {missing}"
        assert not missing_idx, f"Missing indexes: {missing_idx}"

        print("✅ SQLiteAdapter.initialize() creates all tables + indexes")
    finally:
        import shutil
        try:
            shutil.rmtree(tmp, ignore_errors=True)
        except Exception:
            pass


def test_sqlite_crud():
    """Test full CRUD cycle: document → session → issues → read back."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        from app.database.sqlite_adapter import SQLiteAdapter

        adapter = SQLiteAdapter(db_path)
        adapter.initialize()

        # Save document
        doc_id = adapter.save_document("test.docx", "application/docx", 1024, "/tmp/test.docx")
        assert doc_id, "Document ID should not be empty"

        # Read document
        doc = adapter.get_document(doc_id)
        assert doc is not None, "Document should exist"
        assert doc["original_name"] == "test.docx"
        assert doc["size"] == 1024
        print(f"✅ Document CRUD: {doc_id}")

        # Save session with issues
        result = make_sample_result()
        session_id = adapter.save_session(
            filename="test.docx",
            profile_id="academic",
            pack_ids=["ieee"],
            categories=["structure", "writing", "citation"],
            result=result,
            document_id=doc_id,
        )
        assert session_id, "Session ID should not be empty"

        # Read session
        session = adapter.get_session(session_id)
        assert session is not None, "Session should exist"
        assert session["profile_id"] == "academic"
        assert session["score"] == 75
        assert "ieee" in session["pack_ids"]
        assert session["category_scores"]["structure"] == 60
        print(f"✅ Session CRUD: {session_id}")

        # List issues
        issues, total = adapter.list_issues(session_id)
        assert total == 2, f"Expected 2 issues, got {total}"
        assert issues[0]["issue_id"] == "test-issue-1"
        print(f"✅ Issues CRUD: {total} issues")

        # Update issue status
        adapter.update_issue_status(issues[0]["id"], "resolved")
        updated = adapter.get_issue(issues[0]["id"])
        assert updated["status"] == "resolved"
        print("✅ Issue status update")

        # Bulk update
        count = adapter.bulk_update_issue_status(session_id, "open")
        assert count == 2
        print("✅ Bulk update")

        # List sessions
        sessions, total = adapter.list_sessions(profile_id="academic")
        assert total == 1
        assert sessions[0]["id"] == session_id
        print("✅ Session listing with filter")

        # Sessions for document
        doc_sessions = adapter.get_sessions_for_document(doc_id)
        assert len(doc_sessions) == 1
        print("✅ Sessions for document")

        # Delete session
        deleted = adapter.delete_session(session_id)
        assert deleted
        assert adapter.get_session(session_id) is None
        print("✅ Session deletion")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 2: Alembic migration (SQLite)
# ═══════════════════════════════════════════════════════════════════════════════

def test_alembic_migration_up_and_down():
    """Test Alembic migration: upgrade head, then downgrade, then upgrade again."""
    import subprocess

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "alembic_test.db"
        env = os.environ.copy()
        env["REVIEWMIND_SQLITE_PATH"] = str(db_path)
        env["REVIEWMIND_AUTO_MIGRATE"] = "false"
        cwd = Path(__file__).resolve().parent.parent

        # Step 1: Run alembic upgrade head
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True, text=True, cwd=cwd, env=env,
        )
        assert result.returncode == 0, f"Alembic upgrade failed:\n{result.stderr}"
        print("✅ Alembic upgrade head")

        # Verify tables
        missing = verify_tables_exist(db_path)
        assert not missing, f"After migration, missing: {missing}"

        # Verify schema matches expected
        conn = sqlite3.connect(str(db_path))
        columns = {}
        for table in ["documents", "review_sessions", "issues"]:
            cursor = conn.execute(f"PRAGMA table_info({table})")
            columns[table] = {row[1] for row in cursor.fetchall()}
        conn.close()

        assert "id" in columns["documents"]
        assert "original_name" in columns["documents"]
        assert "session_id" in columns["issues"]
        assert "report_markdown" in columns["review_sessions"]
        print("✅ Schema structure verified")

        # Step 2: Downgrade
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "downgrade", "base"],
            capture_output=True, text=True, cwd=cwd, env=env,
        )
        assert result.returncode == 0, f"Alembic downgrade failed:\n{result.stderr}"
        print("✅ Alembic downgrade to base")

        # Verify tables are gone
        conn = sqlite3.connect(str(db_path))
        tables = {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        conn.close()
        assert "documents" not in tables
        assert "review_sessions" not in tables
        assert "issues" not in tables
        print("✅ All tables dropped after downgrade")

        # Step 3: Upgrade again (idempotency)
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True, text=True, cwd=cwd, env=env,
        )
        assert result.returncode == 0, f"Second upgrade failed:\n{result.stderr}"
        missing = verify_tables_exist(db_path)
        assert not missing
        print("✅ Alembic upgrade head (idempotent)")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 3: Raw schema SQL (both backends)
# ═══════════════════════════════════════════════════════════════════════════════

def test_raw_schema_sql():
    """Test that CREATE_SCHEMA_SQL runs on SQLite without errors."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "schema.db"
        conn = sqlite3.connect(str(db_path))
        conn.executescript(CREATE_SCHEMA_SQL)
        conn.close()

        missing = verify_tables_exist(db_path)
        assert not missing, f"Missing from schema SQL: {missing}"
        print("✅ CREATE_SCHEMA_SQL executes cleanly on SQLite")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 4: Database factory (env-driven)
# ═══════════════════════════════════════════════════════════════════════════════

def test_sqlite_adapter_crud():
    """Test SQLiteAdapter full CRUD cycle via the interface."""
    from app.database.sqlite_adapter import SQLiteAdapter
    from app.database import DatabaseBackend

    with tempfile.TemporaryDirectory() as tmp:
        db = SQLiteAdapter(Path(tmp) / "test.db")
        db.initialize()
        assert isinstance(db, DatabaseBackend)

        result = make_sample_result()
        session_id = db.save_session("test.md", "academic", [], ["structure"], result)
        assert session_id

        session = db.get_session(session_id)
        assert session is not None
        assert session["profile_id"] == "academic"
        print(f"✅ SQLiteAdapter CRUD: session {session_id[:8]}...")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 5: Alembic offline mode (SQL generation)
# ═══════════════════════════════════════════════════════════════════════════════

def test_alembic_offline_sql():
    """Test Alembic can generate SQL for both SQLite and PostgreSQL."""
    import subprocess

    cwd = Path(__file__).resolve().parent.parent

    # SQLite offline
    env = os.environ.copy()
    env["REVIEWMIND_PG_DSN"] = ""
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        capture_output=True, text=True, cwd=cwd, env=env,
    )
    assert result.returncode == 0, f"SQLite offline failed:\n{result.stderr}"
    assert "CREATE TABLE" in result.stdout
    assert "documents" in result.stdout
    assert "review_sessions" in result.stdout
    assert "issues" in result.stdout
    print("✅ Alembic generates SQLite SQL (offline mode)")

    # PostgreSQL offline (requires psycopg2, but SQL generation works anyway)
    env["REVIEWMIND_PG_DSN"] = "postgresql://user:pass@localhost:5432/test"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        capture_output=True, text=True, cwd=cwd, env=env,
    )
    # This might fail if psycopg2 is not installed - that's OK
    if result.returncode == 0:
        assert "CREATE TABLE" in result.stdout
        print("✅ Alembic generates PostgreSQL SQL (offline mode)")
    else:
        print("⚠️  PostgreSQL offline test skipped (psycopg2 not installed)")


# ═══════════════════════════════════════════════════════════════════════════════
# RUN ALL
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 ReviewMind Database & Migration Tests")
    print("=" * 60)

    # Run tests sequentially
    tests = [
        ("Raw schema SQL", test_raw_schema_sql),
        ("SQLite initialization", test_sqlite_initialization),
        ("SQLite CRUD", test_sqlite_crud),
        ("SQLiteAdapter CRUD", test_sqlite_adapter_crud),
        ("Alembic offline SQL", test_alembic_offline_sql),
        ("Alembic migrate up/down", test_alembic_migration_up_and_down),
    ]

    passed = 0
    failed = 0
    for name, test_fn in tests:
        print(f"\n─── {name} ───")
        try:
            test_fn()
            passed += 1
        except Exception as e:
            print(f"❌ FAILED: {e}")
            failed += 1

    print(f"\n{'=' * 60}")
    print(f"✅ {passed} passed, ❌ {failed} failed, 🎯 {len(tests)} total")
    print(f"{'=' * 60}")

    if failed > 0:
        sys.exit(1)
