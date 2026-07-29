"""Clerk authentication webhook and JWT verification middleware."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.config import settings
from app.security import audit_log, verify_svix_webhook, WebhookVerificationError

logger = logging.getLogger(__name__)

_JWKS_TTL_SECONDS = 15 * 60
_jwks_cache: dict[str, Any] | None = None
_jwks_cache_expires_at = 0.0
_jwks_lock = asyncio.Lock()


async def _get_clerk_jwks(*, force_refresh: bool = False) -> dict[str, Any]:
    """Return cached Clerk signing keys and refresh safely on rotation."""
    global _jwks_cache, _jwks_cache_expires_at
    now = time.monotonic()
    if not force_refresh and _jwks_cache and now < _jwks_cache_expires_at:
        return _jwks_cache

    async with _jwks_lock:
        now = time.monotonic()
        if not force_refresh and _jwks_cache and now < _jwks_cache_expires_at:
            return _jwks_cache
        if not settings.llm.clerk_domain:
            raise ValueError("CLERK_DOMAIN is not configured")
        import httpx

        url = f"https://{settings.llm.clerk_domain}/.well-known/jwks.json"
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=False) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()
        if not payload.get("keys"):
            raise ValueError("Clerk JWKS response contains no signing keys")
        _jwks_cache = payload
        _jwks_cache_expires_at = time.monotonic() + _JWKS_TTL_SECONDS
        return payload

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ── Clerk Webhook ────────────────────────────────────────────────────────────


from app.database import create_database
database = create_database()

@router.post("/webhook")
async def clerk_webhook(request: Request) -> dict[str, Any]:
    """Receive Clerk webhook events (user.created, user.updated, user.deleted).

    In production, verify the webhook signature using CLERK_WEBHOOK_SECRET.
    For now, log and acknowledge events.
    """
    body = await request.body()
    webhook_secret = settings.llm.clerk_webhook_secret
    if webhook_secret:
        try:
            verify_svix_webhook(
                body,
                message_id=request.headers.get("svix-id", ""),
                timestamp=request.headers.get("svix-timestamp", ""),
                signature_header=request.headers.get("svix-signature", ""),
                secret=webhook_secret,
            )
        except WebhookVerificationError as error:
            audit_log.record(
                actor_id="clerk", action="auth.webhook", resource_type="identity",
                outcome="denied", metadata={"reason": str(error)},
            )
            raise HTTPException(status_code=401, detail="Invalid webhook signature.") from error
    elif settings.llm.clerk_secret_key:
        raise HTTPException(status_code=503, detail="Webhook verification is not configured.")

    payload = json.loads(body)
    event_type = payload.get("type", "unknown")
    data = payload.get("data", {})

    logger.info(f"Clerk webhook: {event_type} — user={data.get('id', 'unknown')}")

    if event_type in ("user.created", "user.updated"):
        user_id = data.get("id")
        email = data.get("email_addresses", [{}])[0].get("email_address", "")
        first_name = data.get("first_name") or ""
        last_name = data.get("last_name") or ""
        name = f"{first_name} {last_name}".strip() or "Unknown User"
        avatar_url = data.get("image_url", "")
        
        if user_id and email:
            database.upsert_user(id=user_id, email=email, name=name, avatar_url=avatar_url)
            logger.info(f"User synced: {email}")

    elif event_type == "user.deleted":
        logger.info(f"User deleted: {data.get('id')}")
        # Note: We keep users in the local DB to preserve review history, 
        # or implement a soft delete here if required.

    audit_log.record(
        actor_id="clerk", action=f"auth.{event_type}", resource_type="user",
        resource_id=str(data.get("id", "")),
    )
    return {"received": True, "type": event_type}


# ── JWT Verification Middleware (optional, for production) ───────────────────


async def verify_clerk_session(request: Request) -> dict[str, Any]:
    """Optional: Verify Clerk session JWT from Authorization header.

    Usage: add `Depends(verify_clerk_session)` to protected routes.
    When CLERK_SECRET_KEY is not set, this is a no-op (development mode).
    """
    if not settings.llm.clerk_secret_key:
        if settings.app.allow_anonymous:
            return {"user_id": None, "role": "admin"}
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Authentication is not configured.")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )

    try:
        token = auth_header.removeprefix("Bearer ").strip()
        from jose import jwk, jwt
        from jose.constants import Algorithms

        header = jwt.get_unverified_header(token)
        key_id = header.get("kid")
        if not key_id:
            raise ValueError("Token key ID is missing")

        jwks = await _get_clerk_jwks()
        key_data = next((item for item in jwks.get("keys", []) if item.get("kid") == key_id), None)
        if key_data is None:
            # Clerk may have rotated keys while our cache was warm.
            jwks = await _get_clerk_jwks(force_refresh=True)
            key_data = next((item for item in jwks.get("keys", []) if item.get("kid") == key_id), None)
        if key_data is None:
            raise ValueError("No matching Clerk signing key found")
        key = jwk.construct(key_data, algorithm=Algorithms.RS256)

        payload = jwt.decode(
            token,
            key,
            algorithms=[Algorithms.RS256],
            audience=settings.llm.clerk_audience or None,
            issuer=f"https://{settings.llm.clerk_domain}",
            options={"verify_aud": bool(settings.llm.clerk_audience)},
        )
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("Token subject is missing")
        role = payload.get("role") or payload.get("public_metadata", {}).get("role", "user")
        audit_log.record(
            actor_id=user_id, action="auth.session_verified", resource_type="session"
        )
        return {"user_id": user_id, "role": role}

    except Exception as e:
        logger.warning(f"Clerk JWT verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session.",
        )


# ── Sync dependency for endpoints that need user_id ────────────────────────


async def get_current_user_id(request: Request) -> str | None:
    """Return the verified Clerk user ID, or anonymous only when explicitly enabled."""
    session = await verify_clerk_session(request)
    return session["user_id"]


def require_resource_owner(
    resource: dict[str, Any] | None,
    user_id: str | None,
    detail: str = "Resource not found.",
) -> dict[str, Any]:
    """Hide resources not owned by the active account, including legacy NULL-owned rows."""
    if resource is None or (user_id is not None and resource.get("user_id") != user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    return resource

# ── Sync User on Login (frontend calls this) ──────────────────────────────


from pydantic import BaseModel


class SyncUserBody(BaseModel):
    name: str = ""
    email: str = ""
    avatar_url: str = ""


@router.post("/sync")
def sync_user(
    body: SyncUserBody,
    user_id: str | None = Depends(get_current_user_id),
) -> dict[str, Any]:
    """
    Sync the authenticated user's profile to the local database.
    Called by the frontend whenever a user logs in or their profile changes.
    """
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    database.upsert_user(
        id=user_id,
        email=body.email,
        name=body.name or "Unknown User",
        avatar_url=body.avatar_url,
    )
    logger.info(f"User synced: {user_id} — {body.email}")

    return {
        "synced": True,
        "user_id": user_id,
    }


# ── User Info Endpoint ───────────────────────────────────────────────────────


@router.get("/me")
async def get_current_user(session: dict[str, Any] = Depends(verify_clerk_session)) -> dict[str, Any]:
    """Get the current authenticated user's info."""
    return {
        "authenticated": True,
        "user_id": session.get("user_id"),
        "role": session.get("role", "user"),
    }
