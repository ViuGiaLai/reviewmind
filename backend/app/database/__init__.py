from functools import lru_cache

from .backend import DatabaseBackend
from app.config import settings

_adapters: set[DatabaseBackend] = set()


@lru_cache(maxsize=4)
def _create_database(dsn: str, min_pool_size: int, max_pool_size: int, statement_timeout_ms: int) -> DatabaseBackend:
    from .postgres_adapter import PostgresAdapter

    backend = PostgresAdapter(
        dsn=dsn,
        min_pool_size=min_pool_size,
        max_pool_size=max_pool_size,
        statement_timeout_ms=statement_timeout_ms,
    )
    backend.initialize()
    _adapters.add(backend)
    return backend


def create_database() -> DatabaseBackend:
    """Return one pooled PostgreSQL adapter per process/configuration."""
    dsn = settings.database.postgres_dsn
    if not dsn:
        raise RuntimeError(
            "REVIEWMIND_PG_DSN is not configured. "
            "Set REVIEWMIND_PG_DSN=postgresql://user:pass@host:5432/dbname "
            "in your .env file to use PostgreSQL."
        )
    core = max(1, settings.database.postgres_pool_size)
    maximum = max(core, core + max(0, settings.database.postgres_max_overflow))
    return _create_database(
        dsn, min(2, core), maximum, settings.performance.database_statement_timeout_ms
    )


def close_database() -> None:
    """Close all cached adapters, mainly for graceful process shutdown."""
    for adapter in list(_adapters):
        close = getattr(adapter, "close", None)
        if close:
            close()
    _adapters.clear()
    _create_database.cache_clear()


__all__ = ["DatabaseBackend", "create_database", "close_database"]