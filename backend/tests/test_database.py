"""Tests for PostgreSQL database backend.

Run with:
    REVIEWMIND_PG_DSN=postgresql://user:pass@localhost:5432/reviewmind_test pytest tests/test_database.py -v

Or directly:
    REVIEWMIND_PG_DSN=postgresql://user:pass@localhost:5432/reviewmind_test python tests/test_database.py
"""

from __future__ import annotations

import json
import os
import sys
import types
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


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 1: PostgresAdapter reconnects after connection is closed
# ═══════════════════════════════════════════════════════════════════════════════

def test_postgres_adapter_reconnects_after_connection_is_closed(monkeypatch):
    class FakeCursor:
        def __init__(self, conn):
            self.conn = conn
        def execute(self, *args, **kwargs):
            if self.conn.closed:
                raise RuntimeError("connection already closed")
        def fetchone(self):
            return {"id": "u1", "email": "a@example.com", "name": "A", "avatar_url": ""}
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeConnection:
        def __init__(self, dsn):
            self.dsn = dsn
            self.closed = False
        def cursor(self, *args, **kwargs):
            if self.closed:
                raise RuntimeError("connection already closed")
            return FakeCursor(self)
        def commit(self):
            pass
        def rollback(self):
            pass
        def close(self):
            self.closed = True
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            self.close()
            return False

    created = []

    class FakePsycopgModule(types.ModuleType):
        def __init__(self):
            super().__init__("psycopg2")
            self.extras = types.SimpleNamespace(RealDictCursor=object)

        @staticmethod
        def connect(dsn):
            conn = FakeConnection(dsn)
            created.append(conn)
            return conn

    monkeypatch.setitem(sys.modules, "psycopg2", FakePsycopgModule())
    monkeypatch.setitem(sys.modules, "psycopg2.extras", types.SimpleNamespace(RealDictCursor=object))

    from app.database import postgres_adapter as postgres_module

    monkeypatch.setattr(postgres_module, "pg_pool", None)
    monkeypatch.setattr(postgres_module.psycopg2, "connect", FakePsycopgModule.connect)
    adapter = postgres_module.PostgresAdapter("postgresql://test")
    assert adapter.get_user("u1") is not None
    assert adapter.get_user("u1") is not None
    assert len(created) >= 2
    print("✅ PostgresAdapter uses a fresh connection each time")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 2: Database factory (requires REVIEWMIND_PG_DSN)
# ═══════════════════════════════════════════════════════════════════════════════

def test_factory_requires_pg_dsn(monkeypatch):
    """Test that create_database() raises when REVIEWMIND_PG_DSN is not set."""
    from app.config import settings
    from app.database import create_database

    # Mock the singleton's postgres_dsn to empty string
    monkeypatch.setattr(settings.database, "postgres_dsn", "")

    try:
        create_database()
        assert False, "Should have raised RuntimeError"
    except RuntimeError as e:
        assert "REVIEWMIND_PG_DSN" in str(e)
        print("✅ Factory raises RuntimeError when PG_DSN is missing")


# ═══════════════════════════════════════════════════════════════════════════════
# RUN ALL
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 ReviewMind PostgreSQL Database Tests")
    print("=" * 60)

    tests = [
        ("PostgresAdapter reconnect", test_postgres_adapter_reconnects_after_connection_is_closed),
        ("Factory requires PG_DSN", test_factory_requires_pg_dsn),
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
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'=' * 60}")
    print(f"✅ {passed} passed, ❌ {failed} failed, 🎯 {len(tests)} total")
    print(f"{'=' * 60}")

    if failed > 0:
        sys.exit(1)
