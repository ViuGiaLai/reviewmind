import json
import logging

from app.operations.alerts import AlertEvaluator
from app.operations.logging import JsonFormatter, request_id_var
from app.operations.metrics import MetricRegistry, MetricsMiddleware
from app.operations.version import build_version_info


def test_metrics_are_prometheus_compatible_and_bounded() -> None:
    registry = MetricRegistry()
    registry.increment(
        "reviewmind_http_requests_total",
        method="GET",
        route="/reviews",
        status="200",
    )
    output = registry.render_prometheus()
    assert "reviewmind_uptime_seconds" in output
    assert 'method="GET"' in output
    assert MetricsMiddleware._route_label(
        "/api/sessions/123e4567-e89b-12d3-a456-426614174000/autofix"
    ) == "/api/sessions/{id}/autofix"


def test_structured_logging_includes_request_correlation() -> None:
    formatter = JsonFormatter()
    token = request_id_var.set("request-123")
    try:
        record = logging.LogRecord(
            "reviewmind.test", logging.INFO, __file__, 1, "completed", (), None
        )
        payload = json.loads(formatter.format(record))
    finally:
        request_id_var.reset(token)
    assert payload["request_id"] == "request-123"
    assert payload["message"] == "completed"


def test_alert_evaluator_detects_operational_risk() -> None:
    alerts = AlertEvaluator().evaluate({
        "api_error_rate": 0.10,
        "api_p95_seconds": 3.0,
        "autofix_failure_rate": 0.0,
        "storage_utilization": 0.5,
        "queue_depth": 2,
        "ai_available": 0,
    })
    assert {alert.code for alert in alerts} == {
        "api_error_rate", "api_p95_seconds", "ai_available"
    }


def test_version_info_contains_reproducibility_fields() -> None:
    version = build_version_info()
    assert {"platform", "api", "rules", "prompts", "commit", "environment"} <= version.keys()
