from .backend import DatabaseBackend
from .repository import ReviewRepository
from .sqlite_adapter import SQLiteAdapter
from app.config import settings


def create_database() -> DatabaseBackend:
    """Factory: create the appropriate database backend based on config."""
    if settings.database.is_postgres:
        from .postgres_adapter import PostgresAdapter
        backend = PostgresAdapter(
            dsn=settings.database.postgres_dsn,
        )
    else:
        backend = SQLiteAdapter(settings.database.sqlite_path)

    backend.initialize()
    return backend


__all__ = ["DatabaseBackend", "ReviewRepository", "SQLiteAdapter", "create_database"]
