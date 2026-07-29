from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OperationalAlert:
    code: str
    severity: str
    message: str
    value: float
    threshold: float


class AlertEvaluator:
    """Pure threshold evaluator; delivery is delegated to deployment tooling."""

    def evaluate(self, snapshot: dict[str, float]) -> list[OperationalAlert]:
        alerts: list[OperationalAlert] = []
        self._above(alerts, snapshot, "api_error_rate", 0.05, "critical")
        self._above(alerts, snapshot, "api_p95_seconds", 2.0, "warning")
        self._above(alerts, snapshot, "autofix_failure_rate", 0.20, "warning")
        self._above(alerts, snapshot, "storage_utilization", 0.85, "warning")
        self._above(alerts, snapshot, "queue_depth", 1000, "warning")
        if snapshot.get("ai_available", 1) < 1:
            alerts.append(OperationalAlert(
                code="ai_available",
                severity="warning",
                message="AI provider is unavailable; rule-only review remains active.",
                value=snapshot.get("ai_available", 0),
                threshold=1,
            ))
        return alerts

    @staticmethod
    def _above(
        alerts: list[OperationalAlert],
        snapshot: dict[str, float],
        key: str,
        threshold: float,
        severity: str,
    ) -> None:
        value = snapshot.get(key)
        if value is not None and value > threshold:
            alerts.append(OperationalAlert(
                code=key,
                severity=severity,
                message=f"{key} exceeded operational threshold.",
                value=value,
                threshold=threshold,
            ))


alert_evaluator = AlertEvaluator()
