from .backend import DatabaseBackend
from app.config import settings


def create_database() -> DatabaseBackend:
    """Factory: create a PostgreSQL database backend.

    Requires REVIEWMIND_PG_DSN to be set in the environment.
    """
    from .postgres_adapter import PostgresAdapter

    if not settings.database.postgres_dsn:
        raise RuntimeError(
            "REVIEWMIND_PG_DSN is not configured. "
            "Set REVIEWMIND_PG_DSN=postgresql://user:pass@host:5432/dbname "
            "in your .env file to use PostgreSQL."
        )

    backend = PostgresAdapter(dsn=settings.database.postgres_dsn)
    backend.initialize()
    return backend


__all__ = ["DatabaseBackend", "create_database"]
