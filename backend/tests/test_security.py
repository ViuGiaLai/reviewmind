import asyncio
import base64
import hashlib
import hmac
import time
from datetime import datetime, timedelta, timezone

import pytest
from starlette.requests import Request

from app.security import (
    AuditLog,
    DataClass,
    Permission,
    Principal,
    RetentionPolicy,
    Role,
    WebhookVerificationError,
    verify_svix_webhook,
)


def _signed_webhook(body: bytes, secret: str, timestamp: int) -> str:
    key = base64.b64decode(secret.removeprefix("whsec_"))
    signed = f"msg-1.{timestamp}.".encode() + body
    digest = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()
    return f"v1,{digest}"


def test_webhook_signature_and_replay_protection() -> None:
    body = b'{"type":"user.created"}'
    secret = "whsec_" + base64.b64encode(b"test-secret").decode()
    timestamp = int(time.time())
    signature = _signed_webhook(body, secret, timestamp)
    verify_svix_webhook(
        body,
        message_id="msg-1",
        timestamp=str(timestamp),
        signature_header=signature,
        secret=secret,
    )
    with pytest.raises(WebhookVerificationError):
        verify_svix_webhook(
            body + b"tampered",
            message_id="msg-1",
            timestamp=str(timestamp),
            signature_header=signature,
            secret=secret,
        )
    with pytest.raises(WebhookVerificationError):
        verify_svix_webhook(
            body,
            message_id="msg-1",
            timestamp=str(timestamp - 1000),
            signature_header=signature,
            secret=secret,
        )


def test_audit_log_redacts_secrets_and_verifies_hash_chain() -> None:
    log = AuditLog()
    event = log.record(
        actor_id="user-1",
        action="review.completed",
        resource_type="review",
        metadata={"token": "secret-token", "score": 90},
    )
    assert event.metadata["token"] == "[REDACTED]"
    assert event.metadata["score"] == "90"
    assert log.verify_chain()


def test_role_permissions_use_least_privilege() -> None:
    viewer = Principal("viewer-1", Role.VIEWER)
    editor = Principal("editor-1", Role.EDITOR)
    assert viewer.can(Permission.VIEW_DOCUMENT)
    assert not viewer.can(Permission.APPLY_AUTOFIX)
    assert editor.can(Permission.APPLY_AUTOFIX)
    assert not editor.can(Permission.MANAGE_SECURITY)


def test_retention_honors_expiry_and_legal_hold() -> None:
    policy = RetentionPolicy(days={item: 30 for item in DataClass})
    created = datetime.now(timezone.utc) - timedelta(days=31)
    assert policy.is_expired(DataClass.DOCUMENT, created)
    assert not policy.is_expired(DataClass.DOCUMENT, created, legal_hold=True)


def test_production_user_dependency_uses_verified_session(monkeypatch) -> None:
    from app.api import auth

    monkeypatch.setattr(auth.settings.llm, "clerk_secret_key", "configured")
    called = {"verified": False}

    async def verified(_request):
        called["verified"] = True
        return {"user_id": "verified-user", "role": "editor"}

    monkeypatch.setattr(auth, "verify_clerk_session", verified)
    request = Request({"type": "http", "headers": []})
    user_id = asyncio.run(auth.get_current_user_id(request))
    assert called["verified"]
    assert user_id == "verified-user"

def test_development_user_dependency_is_anonymous_only_when_explicit(monkeypatch) -> None:
    from app.api import auth

    monkeypatch.setattr(auth.settings.llm, "clerk_secret_key", "")
    monkeypatch.setattr(auth.settings.app, "allow_anonymous", True)
    request = Request({"type": "http", "headers": []})
    assert asyncio.run(auth.get_current_user_id(request)) is None


def test_missing_auth_configuration_is_secure_by_default(monkeypatch) -> None:
    from fastapi import HTTPException
    from app.api import auth

    monkeypatch.setattr(auth.settings.llm, "clerk_secret_key", "")
    monkeypatch.setattr(auth.settings.app, "allow_anonymous", False)
    request = Request({"type": "http", "headers": []})
    with pytest.raises(HTTPException) as exc:
        asyncio.run(auth.get_current_user_id(request))
    assert exc.value.status_code == 503


def test_resource_owner_rejects_other_and_legacy_accounts() -> None:
    from fastapi import HTTPException
    from app.api.auth import require_resource_owner

    assert require_resource_owner({"id": "owned", "user_id": "user-a"}, "user-a")["id"] == "owned"
    for resource in ({"id": "other", "user_id": "user-b"}, {"id": "legacy", "user_id": None}):
        with pytest.raises(HTTPException) as exc:
            require_resource_owner(resource, "user-a")
        assert exc.value.status_code == 404

def test_clerk_session_uses_python_jose_unverified_header(monkeypatch) -> None:
    from jose import jwk, jwt
    from app.api import auth

    async def jwks(*, force_refresh: bool = False):
        return {"keys": [{"kid": "key-1", "kty": "RSA"}]}

    monkeypatch.setattr(auth.settings.llm, "clerk_secret_key", "configured")
    monkeypatch.setattr(auth.settings.llm, "clerk_domain", "clerk.example")
    monkeypatch.setattr(auth, "_get_clerk_jwks", jwks)
    monkeypatch.setattr(jwt, "get_unverified_header", lambda token: {"kid": "key-1"})
    monkeypatch.setattr(jwt, "decode", lambda *args, **kwargs: {"sub": "user-1", "role": "user"})
    monkeypatch.setattr(jwk, "construct", lambda *args, **kwargs: object())
    monkeypatch.setattr(auth.audit_log, "record", lambda **kwargs: None)

    request = Request({
        "type": "http",
        "method": "GET",
        "path": "/api/evaluation-profiles/options",
        "headers": [(b"authorization", b"Bearer valid-token")],
    })
    session = asyncio.run(auth.verify_clerk_session(request))
    assert session == {"user_id": "user-1", "role": "user"}