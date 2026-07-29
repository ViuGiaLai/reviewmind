from __future__ import annotations

import re
import threading
import time
from collections import defaultdict
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from .logging import request_id_var


class MetricRegistry:
    """Small dependency-free Prometheus registry for core operational signals."""

    DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

    def __init__(self) -> None:
        self.started_at = time.time()
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
        self._lock = threading.Lock()

    def increment(self, name: str, value: float = 1, **labels: str) -> None:
        key = (name, tuple(sorted((key, str(val)) for key, val in labels.items())))
        with self._lock:
            self._counters[key] += value

    def observe(self, name: str, value: float, **labels: str) -> None:
        """Record histogram buckets so Prometheus can calculate p50/p95/p99."""
        self.increment(f"{name}_sum", value, **labels)
        self.increment(f"{name}_count", 1, **labels)
        for boundary in self.DEFAULT_BUCKETS:
            if value <= boundary:
                self.increment(f"{name}_bucket", 1, **labels, le=f"{boundary:g}")
        self.increment(f"{name}_bucket", 1, **labels, le="+Inf")

    def render_prometheus(self) -> str:
        lines = [
            "# TYPE reviewmind_uptime_seconds gauge",
            f"reviewmind_uptime_seconds {max(0, time.time() - self.started_at):.3f}",
        ]
        with self._lock:
            entries = list(self._counters.items())
        for (name, labels), value in sorted(entries):
            suffix = ""
            if labels:
                encoded = ",".join(
                    f'{key}="{self._escape(val)}"' for key, val in labels
                )
                suffix = "{" + encoded + "}"
            lines.append(f"{name}{suffix} {value}")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _escape(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


metrics = MetricRegistry()


class MetricsMiddleware(BaseHTTPMiddleware):
    _REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,100}$")

    async def dispatch(self, request: Request, call_next):
        supplied = request.headers.get("x-request-id", "")
        request_id = supplied if self._REQUEST_ID.fullmatch(supplied) else str(uuid4())
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            elapsed_ms = (time.perf_counter() - started) * 1000
            response.headers["x-request-id"] = request_id
            response.headers["server-timing"] = f"app;dur={elapsed_ms:.2f}"
            response.headers["x-response-time-ms"] = f"{elapsed_ms:.2f}"
            return response
        finally:
            duration = time.perf_counter() - started
            route = self._route_label(request.url.path)
            metrics.increment(
                "reviewmind_http_requests_total",
                method=request.method,
                route=route,
                status=str(status_code),
            )
            metrics.observe(
                "reviewmind_http_request_duration_seconds",
                duration,
                method=request.method,
                route=route,
            )
            if status_code >= 500:
                metrics.increment("reviewmind_http_errors_total", route=route)
            request_id_var.reset(token)

    @staticmethod
    def _route_label(path: str) -> str:
        # Avoid unbounded labels from UUIDs and user-controlled paths.
        parts = path.strip("/").split("/")
        normalized = [
            "{id}" if len(part) >= 24 and re.fullmatch(r"[A-Za-z0-9-]+", part) else part
            for part in parts[:6]
        ]
        return "/" + "/".join(normalized)
