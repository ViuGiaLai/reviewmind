from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from app.api.routes import api_router
from app.config import settings
from app.database import close_database, create_database
from app.operations import (
    MetricsMiddleware,
    build_version_info,
    configure_structured_logging,
    metrics,
)


configure_structured_logging(logging.DEBUG if settings.app.debug else logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ReviewMind API", version=build_version_info()["platform"])
app.add_middleware(MetricsMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.app.cors_origins,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    allow_credentials=False,
)
app.include_router(api_router)


@app.on_event("shutdown")
def shutdown_resources() -> None:
    close_database()


@app.get("/health", include_in_schema=False)
@app.get("/live", include_in_schema=False)
def liveness() -> dict[str, str]:
    """Process liveness only; it never performs dependency I/O."""
    return {"status": "alive"}


@app.get("/ready", include_in_schema=False)
def readiness() -> JSONResponse:
    """Dependency readiness with a non-200 response when service is unsafe for traffic."""
    from app.storage import LocalStorage, S3Storage, create_storage

    checks: dict[str, bool] = {"database": False, "storage": False}
    try:
        database = create_database()
        database.get_statistics()
        checks["database"] = True
    except Exception:
        logger.exception("Database readiness probe failed")

    try:
        storage = create_storage()
        if isinstance(storage, LocalStorage):
            checks["storage"] = storage.base_path.is_dir()
        elif isinstance(storage, S3Storage):
            storage.client.head_bucket(Bucket=storage.bucket)
            checks["storage"] = True
    except Exception:
        logger.exception("Storage readiness probe failed")

    ready = all(checks.values())
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "ready" if ready else "not_ready", "checks": checks},
    )


@app.get("/metrics", include_in_schema=False)
def prometheus_metrics() -> PlainTextResponse:
    return PlainTextResponse(
        metrics.render_prometheus(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@app.get("/version", include_in_schema=False)
def version() -> dict[str, Any]:
    return build_version_info()