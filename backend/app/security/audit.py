from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class AuditEvent:
    id: str
    occurred_at: str
    actor_id: str
    action: str
    resource_type: str
    resource_id: str
    outcome: str
    metadata: dict[str, Any]
    previous_hash: str
    event_hash: str


class AuditLog:
    """Append-only, hash-chained audit log with secret redaction."""

    _SECRET_KEYS = {
        "authorization", "token", "api_key", "secret", "password",
        "document_text", "content",
    }

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        self._lock = threading.Lock()

    def record(
        self,
        *,
        actor_id: str,
        action: str,
        resource_type: str,
        resource_id: str = "",
        outcome: str = "success",
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        with self._lock:
            previous_hash = self._events[-1].event_hash if self._events else "GENESIS"
            payload = {
                "id": str(uuid4()),
                "occurred_at": datetime.now(timezone.utc).isoformat(),
                "actor_id": actor_id or "anonymous",
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "outcome": outcome,
                "metadata": self._redact(metadata or {}),
                "previous_hash": previous_hash,
            }
            canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
            event = AuditEvent(
                **payload,
                event_hash=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            )
            self._events.append(event)
            return event

    def list(self, limit: int = 100) -> list[AuditEvent]:
        return list(reversed(self._events[-max(0, limit):]))

    def verify_chain(self) -> bool:
        previous_hash = "GENESIS"
        for event in self._events:
            data = asdict(event)
            event_hash = data.pop("event_hash")
            if data["previous_hash"] != previous_hash:
                return False
            canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
            if hashlib.sha256(canonical.encode("utf-8")).hexdigest() != event_hash:
                return False
            previous_hash = event_hash
        return True

    def _redact(self, value: Any, key: str = "") -> Any:
        if key.casefold() in self._SECRET_KEYS:
            return "[REDACTED]"
        if isinstance(value, dict):
            return {str(k): self._redact(v, str(k)) for k, v in value.items()}
        if isinstance(value, list):
            return [self._redact(item) for item in value]
        text = str(value)
        return text[:1000]


audit_log = AuditLog()
