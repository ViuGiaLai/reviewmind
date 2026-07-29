from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, Query

from app.config import settings
from app.security import (
    DataClass,
    Permission,
    Principal,
    audit_log,
    require_permission,
    retention_policy,
)


router = APIRouter(prefix="/api/security", tags=["security"])


@router.get("/status")
def security_status(
    principal: Principal = Depends(require_permission(Permission.MANAGE_SECURITY)),
) -> dict[str, Any]:
    audit_log.record(
        actor_id=principal.user_id,
        action="security.status_viewed",
        resource_type="security",
    )
    return {
        "authentication": {
            "mode": "clerk" if settings.llm.clerk_secret_key else "development",
            "jwt_signature_verification": bool(settings.llm.clerk_secret_key),
            "webhook_signature_verification": bool(settings.llm.clerk_webhook_secret),
        },
        "privacy": {
            "sensitive_data_to_cloud_allowed": settings.llm.allow_sensitive_data,
            "ai_guardrails_enabled": settings.llm.enable_guardrails,
        },
        "retention": {
            data_class.value: days
            for data_class, days in retention_policy.days.items()
        },
        "audit_chain_valid": audit_log.verify_chain(),
    }


@router.get("/audit")
def list_audit_events(
    limit: int = Query(100, ge=1, le=500),
    principal: Principal = Depends(require_permission(Permission.VIEW_AUDIT)),
) -> dict[str, Any]:
    audit_log.record(
        actor_id=principal.user_id,
        action="audit.read",
        resource_type="audit_log",
        metadata={"limit": limit},
    )
    events = audit_log.list(limit)
    return {
        "total": len(events),
        "chain_valid": audit_log.verify_chain(),
        "items": [asdict(event) for event in events],
    }
