from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum


class DataClass(str, Enum):
    DOCUMENT = "document"
    REVIEW = "review"
    AUDIT = "audit"
    AUTOFIX_VERSION = "autofix_version"


@dataclass
class RetentionPolicy:
    days: dict[DataClass, int] = field(default_factory=lambda: {
        DataClass.DOCUMENT: 90,
        DataClass.REVIEW: 365,
        DataClass.AUDIT: 730,
        DataClass.AUTOFIX_VERSION: 365,
    })

    def expires_at(self, data_class: DataClass, created_at: datetime) -> datetime | None:
        retention_days = self.days[data_class]
        if retention_days < 0:
            return None
        return created_at + timedelta(days=retention_days)

    def is_expired(
        self,
        data_class: DataClass,
        created_at: datetime,
        *,
        now: datetime | None = None,
        legal_hold: bool = False,
    ) -> bool:
        if legal_hold:
            return False
        expiry = self.expires_at(data_class, created_at)
        current = now or datetime.now(timezone.utc)
        return bool(expiry and current >= expiry)


retention_policy = RetentionPolicy()
