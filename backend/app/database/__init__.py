from .backend import DatabaseBackend
from .repository import ReviewRepository
from .sqlite_adapter import SQLiteAdapter
from app.config import settings


def create_database() -> DatabaseBackend:
    """Factory: create the appropriate database backend based on config (Postgres only)."""
    from .postgres_adapter import PostgresAdapter
    backend = PostgresAdapter(
        dsn=settings.database.postgres_dsn,
    )
    backend.initialize()
    return backend


__all__ = ["DatabaseBackend", "ReviewRepository", "SQLiteAdapter", "create_database"]
