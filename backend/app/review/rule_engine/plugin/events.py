from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Callable, Mapping


CORE_EVENTS = frozenset({
    "document.uploaded",
    "parser.finished",
    "document_understanding.finished",
    "rule_engine.started",
    "issues.generated",
    "autofix.completed",
    "report.generated",
})


@dataclass(frozen=True)
class PluginEvent:
    name: str
    payload: Mapping[str, Any]
    occurred_at: str


@dataclass(frozen=True)
class EventDelivery:
    plugin_id: str
    event_name: str
    success: bool
    error: str = ""


class PluginEventBus:
    """Synchronous event bus with isolated subscribers and immutable payloads."""

    def __init__(self, is_enabled: Callable[[str], bool] | None = None) -> None:
        self._subscriptions: dict[str, list[tuple[str, Callable[[PluginEvent], None]]]] = {}
        self._is_enabled = is_enabled or (lambda _plugin_id: True)
        self.audit_log: list[EventDelivery] = []

    def subscribe(
        self,
        plugin_id: str,
        event_name: str,
        handler: Callable[[PluginEvent], None],
    ) -> None:
        if event_name not in CORE_EVENTS:
            raise ValueError(f"Unknown core event: {event_name}")
        self._subscriptions.setdefault(event_name, []).append((plugin_id, handler))

    def unsubscribe_plugin(self, plugin_id: str) -> None:
        for event_name in list(self._subscriptions):
            self._subscriptions[event_name] = [
                item for item in self._subscriptions[event_name]
                if item[0] != plugin_id
            ]

    def publish(self, event_name: str, payload: dict[str, Any]) -> list[EventDelivery]:
        if event_name not in CORE_EVENTS:
            raise ValueError(f"Unknown core event: {event_name}")
        event = PluginEvent(
            name=event_name,
            payload=MappingProxyType(dict(payload)),
            occurred_at=datetime.now(timezone.utc).isoformat(),
        )
        deliveries: list[EventDelivery] = []
        for plugin_id, handler in list(self._subscriptions.get(event_name, [])):
            if not self._is_enabled(plugin_id):
                continue
            try:
                handler(event)
                delivery = EventDelivery(plugin_id, event_name, True)
            except Exception as error:
                delivery = EventDelivery(plugin_id, event_name, False, str(error)[:500])
            deliveries.append(delivery)
            self.audit_log.append(delivery)
        return deliveries
