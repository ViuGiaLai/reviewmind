from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

# Load .env from project root (two levels up from this file)
_env_path = Path(__file__).resolve().parents[2] / ".env"
if _env_path.exists():
    load_dotenv(dotenv_path=_env_path, override=True)



@dataclass
class DatabaseSettings:
    """Database configuration."""

    # SQLite (default for development)
    sqlite_path: Path = Path(
        os.getenv("REVIEWMIND_SQLITE_PATH", str(Path(__file__).resolve().parent.parent / "data" / "reviewmind.sqlite3"))
    )

    # PostgreSQL (production)
    postgres_dsn: str = os.getenv("REVIEWMIND_PG_DSN", "")
    postgres_pool_size: int = int(os.getenv("REVIEWMIND_PG_POOL_SIZE", "10"))
    postgres_max_overflow: int = int(os.getenv("REVIEWMIND_PG_MAX_OVERFLOW", "20"))

    # Migration
    auto_migrate: bool = os.getenv("REVIEWMIND_AUTO_MIGRATE", "true").lower() in ("true", "1", "yes")

    @property
    def is_postgres(self) -> bool:
        return bool(self.postgres_dsn)


@dataclass
class StorageSettings:
    """File storage configuration (Cloudflare R2 / S3 only)."""
    
    backend: Literal["s3"] = "s3"

    # S3-compatible storage
    s3_endpoint: str = os.getenv("REVIEWMIND_S3_ENDPOINT", "")
    s3_region: str = os.getenv("REVIEWMIND_S3_REGION", "us-east-1")
    s3_bucket: str = os.getenv("REVIEWMIND_S3_BUCKET", "reviewmind")
    s3_access_key: str = os.getenv("REVIEWMIND_S3_ACCESS_KEY", "")
    s3_secret_key: str = os.getenv("REVIEWMIND_S3_SECRET_KEY", "")
    s3_force_path_style: bool = os.getenv("REVIEWMIND_S3_FORCE_PATH_STYLE", "false").lower() in ("true", "1")

    @property
    def is_s3(self) -> bool:
        return True


@dataclass
class AppSettings:
    """Application-wide settings."""

    debug: bool = os.getenv("REVIEWMIND_DEBUG", "true").lower() in ("true", "1", "yes")
    cors_origins: list[str] = field(default_factory=lambda: [
        o.strip() for o in os.getenv("REVIEWMIND_CORS_ORIGINS", "http://localhost:5173").split(",")
    ])
    max_file_size: int = int(os.getenv("REVIEWMIND_MAX_FILE_SIZE", str(50 * 1024 * 1024)))
    upload_chunk_size: int = int(os.getenv("REVIEWMIND_UPLOAD_CHUNK_SIZE", str(1024 * 1024)))

    # Cleanup
    cleanup_days: int = int(os.getenv("REVIEWMIND_CLEANUP_DAYS", "90"))
    cleanup_enabled: bool = os.getenv("REVIEWMIND_CLEANUP_ENABLED", "false").lower() in ("true", "1")


@dataclass
class LLMSettings:
    """LLM provider configuration (mirrors llm/config.py for backward compat)."""

    # API keys
    gemini_api_key: str = os.getenv("REVIEWMIND_GEMINI_API_KEY", "")
    openrouter_api_key: str = os.getenv("REVIEWMIND_OPENROUTER_API_KEY", "")
    github_token: str = os.getenv("REVIEWMIND_GITHUB_TOKEN", "")
    nvidia_api_key: str = os.getenv("NVIDIA_API_KEY", "")
    cohere_api_key: str = os.getenv("COHERE_API_KEY", "")
    openai_api_key: str = os.getenv("REVIEWMIND_OPENAI_API_KEY", "")
    anthropic_api_key: str = os.getenv("REVIEWMIND_ANTHROPIC_API_KEY", "")

    # Runtime
    enabled: bool = True
    max_tokens: int = int(os.getenv("REVIEWMIND_LLM_MAX_TOKENS", "4096"))
    temperature: float = float(os.getenv("REVIEWMIND_LLM_TEMPERATURE", "0.3"))
    enable_guardrails: bool = os.getenv("REVIEWMIND_ENABLE_GUARDRAILS", "true").lower() in ("true", "1")
    allow_sensitive_data: bool = os.getenv("REVIEWMIND_ALLOW_SENSITIVE_DATA", "false").lower() in ("true", "1")

    # Clerk authentication
    clerk_secret_key: str = os.getenv("CLERK_SECRET_KEY", "")
    clerk_domain: str = os.getenv("CLERK_DOMAIN", "")

    @property
    def has_any_key(self) -> bool:
        return bool(self.gemini_api_key or self.openrouter_api_key or self.github_token or self.nvidia_api_key or self.cohere_api_key)


@dataclass
class Settings:
    """Root settings object."""

    app: AppSettings = field(default_factory=AppSettings)
    database: DatabaseSettings = field(default_factory=DatabaseSettings)
    storage: StorageSettings = field(default_factory=StorageSettings)
    llm: LLMSettings = field(default_factory=LLMSettings)


# Global singleton
settings = Settings()
