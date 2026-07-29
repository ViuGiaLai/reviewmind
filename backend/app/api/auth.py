"""Clerk authentication webhook and JWT verification middleware."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.config import settings

logger = logging.getLogger(__name__)

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
    payload = await request.json()
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

    return {"received": True, "type": event_type}


# ── JWT Verification Middleware (optional, for production) ───────────────────


async def verify_clerk_session(request: Request) -> dict[str, Any]:
    """Optional: Verify Clerk session JWT from Authorization header.

    Usage: add `Depends(verify_clerk_session)` to protected routes.
    When CLERK_SECRET_KEY is not set, this is a no-op (development mode).
    """
    if not settings.llm.clerk_secret_key:
        # Development mode — no auth required
        return {"user_id": "dev-user", "role": "admin"}

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )

    try:
        token = auth_header.replace("Bearer ", "")
        # Use Clerk's JWKS endpoint to verify the token
        # For production, use `clerk-sdk-python` or manual JWKS verification
        # https://clerk.com/docs/backend-requests/handling/pizzly
        from jose import jwk, jwt
        from jose.constants import Algorithms

        # Get JWKS from Clerk
        import httpx
        jwks_url = f"https://{settings.llm.clerk_domain}/.well-known/jwks.json"
        async with httpx.AsyncClient() as client:
            resp = await client.get(jwks_url)
            jwks = resp.json()

        # Decode and verify the JWT
        header = jwt.get_header(token)
        key = None
        for jwk_key in jwks.get("keys", []):
            if jwk_key.get("kid") == header.get("kid"):
                key = jwk.construct(jwk_key)
                break

        if not key:
            raise ValueError("No matching JWK key found")

        payload = jwt.decode(
            token,
            key,
            algorithms=[Algorithms.RS256],
            audience="",
            issuer=f"https://{settings.llm.clerk_domain}",
        )
        return {"user_id": payload.get("sub"), "role": payload.get("role", "user")}

    except Exception as e:
        logger.warning(f"Clerk JWT verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid session: {e}",
        )


# ── User Info Endpoint ───────────────────────────────────────────────────────


@router.get("/me")
async def get_current_user(session: dict[str, Any] = Depends(verify_clerk_session)) -> dict[str, Any]:
    """Get the current authenticated user's info."""
    return {
        "authenticated": True,
        "user_id": session.get("user_id"),
        "role": session.get("role", "user"),
    }
