from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.upload_utils import read_upload_limited
from app.operations.metrics import MetricRegistry
from app.review.models import DocumentModel
from app.review.profiles import Profile
from app.review.rule_engine.registry import RuleMeta, RuleRegistry
from app.review.models import Severity


class ChunkedUpload:
    def __init__(self, chunks: list[bytes]):
        self.chunks = iter(chunks)

    async def read(self, size: int) -> bytes:
        return next(self.chunks, b"")


def test_upload_limit_stops_before_unbounded_memory_growth() -> None:
    upload = ChunkedUpload([b"a" * 5, b"b" * 6, b""])
    with pytest.raises(HTTPException) as error:
        asyncio.run(read_upload_limited(upload, max_bytes=10, chunk_size=5))  # type: ignore[arg-type]
    assert error.value.status_code == 413


def test_metric_observation_emits_histogram_for_quantiles() -> None:
    registry = MetricRegistry()
    registry.observe("reviewmind_latency_seconds", 0.08, route="/live")
    output = registry.render_prometheus()
    assert 'reviewmind_latency_seconds_bucket{le="0.1",route="/live"} 1.0' in output
    assert 'reviewmind_latency_seconds_bucket{le="+Inf",route="/live"} 1.0' in output


def test_rule_cache_uses_full_document_and_stays_bounded() -> None:
    registry = RuleRegistry()
    registry._cache_max_entries = 2
    calls = 0

    def rule(document, profile, config):
        nonlocal calls
        calls += 1
        return []

    meta = RuleMeta(
        id="performance.cache",
        category="writing",
        name="Cache test",
        description="Cache test",
        severity=Severity.LOW,
        timeout_ms=0,
    )
    registry.register(meta.id, meta, rule)
    registered = registry.get(meta.id)
    assert registered is not None
    profile = Profile(
        id="general", name="General", categories=["writing"], weights={"writing": 100},
        permissions={"writing": 1}, required_sections=[],
    )

    prefix = "x" * 100
    first = DocumentModel("a.md", "text/markdown", prefix + "A", [], [], [])
    second = DocumentModel("b.md", "text/markdown", prefix + "B", [], [], [])
    third = DocumentModel("c.md", "text/markdown", prefix + "C", [], [], [])
    registry._run_single_rule(registered, first, profile, {})
    registry._run_single_rule(registered, first, profile, {})
    registry._run_single_rule(registered, second, profile, {})
    registry._run_single_rule(registered, third, profile, {})

    assert calls == 3
    assert len(registry._cache) == 2


def test_postgres_adapter_reuses_threaded_pool(monkeypatch) -> None:
    from app.database import postgres_adapter as module

    class Cursor:
        def execute(self, statement):
            assert statement.startswith("SET LOCAL statement_timeout")
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False

    class Connection:
        closed = 0
        autocommit = True
        def cursor(self):
            return Cursor()
        def rollback(self):
            return None

    connection = Connection()
    created: list[object] = []

    class Pool:
        def __init__(self, *args, **kwargs):
            created.append(self)
        def getconn(self):
            return connection
        def putconn(self, conn, close=False):
            return None
        def closeall(self):
            return None

    monkeypatch.setattr(
        module,
        "pg_pool",
        SimpleNamespace(ThreadedConnectionPool=Pool, PoolError=RuntimeError),
    )
    adapter = module.PostgresAdapter("postgresql://unused", max_pool_size=4)
    with adapter._connect() as first:
        assert first is connection
    with adapter._connect() as second:
        assert second is connection
    assert len(created) == 1
