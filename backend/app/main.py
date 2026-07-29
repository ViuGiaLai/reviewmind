from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.config import settings
from app.database import create_database

app = FastAPI(title="ReviewMind API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.app.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)
app.include_router(api_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, Any]:
    """Readiness check: verifies database and storage are accessible."""
    from app.storage import create_storage
    checks = {"database": False, "storage": False}
    try:
        db = create_database()
        db.initialize()
        checks["database"] = True
    except Exception as e:
        checks["database_error"] = str(e)
    try:
        storage = create_storage()
        checks["storage"] = True
    except Exception as e:
        checks["storage_error"] = str(e)
    all_ok = all(v for k, v in checks.items() if not k.endswith("_error"))
    return {"status": "ready" if all_ok else "degraded", "checks": checks}
