from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class PluginPermission(str, Enum):
    READ_DOCUMENT = "read_document"
    ADD_RULE = "add_rule"
    ADD_KNOWLEDGE_PACK = "add_knowledge_pack"
    ADD_REPORT_SECTION = "add_report_section"
    ADD_AUTOFIX_STRATEGY = "add_autofix_strategy"
    CALL_AI = "call_ai"
    EXPORT = "export"
    MODIFY_DOCUMENT = "modify_document"
    ACCESS_USER_DATA = "access_user_data"
    ACCESS_SETTINGS = "access_settings"


class ExtensionPoint(str, Enum):
    RULE = "rule"
    KNOWLEDGE_PACK = "knowledge_pack"
    REPORT_SECTION = "report_section"
    AUTOFIX_STRATEGY = "autofix_strategy"
    EXPORTER = "exporter"


class PluginPermissionError(PermissionError):
    pass


@dataclass(frozen=True)
class PluginContribution:
    plugin_id: str
    extension_point: ExtensionPoint
    contribution_id: str
    handler: Callable[..., Any]
    metadata: dict[str, Any] = field(default_factory=dict)


class ExtensionAPI:
    """Narrow capability API exposed to plugins instead of internal core objects."""

    _REQUIRED_PERMISSION = {
        ExtensionPoint.RULE: PluginPermission.ADD_RULE,
        ExtensionPoint.KNOWLEDGE_PACK: PluginPermission.ADD_KNOWLEDGE_PACK,
        ExtensionPoint.REPORT_SECTION: PluginPermission.ADD_REPORT_SECTION,
        ExtensionPoint.AUTOFIX_STRATEGY: PluginPermission.ADD_AUTOFIX_STRATEGY,
        ExtensionPoint.EXPORTER: PluginPermission.EXPORT,
    }

    def __init__(self) -> None:
        self._grants: dict[str, frozenset[PluginPermission]] = {}
        self._contributions: dict[ExtensionPoint, dict[str, PluginContribution]] = {
            point: {} for point in ExtensionPoint
        }

    def grant(self, plugin_id: str, permissions: list[str]) -> None:
        parsed: set[PluginPermission] = set()
        for permission in permissions:
            try:
                parsed.add(PluginPermission(permission))
            except ValueError as error:
                raise PluginPermissionError(
                    f"Unknown permission '{permission}' requested by '{plugin_id}'."
                ) from error
        self._grants[plugin_id] = frozenset(parsed)

    def for_plugin(self, plugin_id: str) -> "BoundExtensionAPI":
        return BoundExtensionAPI(self, plugin_id)

    def register(
        self,
        plugin_id: str,
        extension_point: ExtensionPoint,
        contribution_id: str,
        handler: Callable[..., Any],
        metadata: dict[str, Any] | None = None,
    ) -> PluginContribution:
        self.require(plugin_id, self._REQUIRED_PERMISSION[extension_point])
        key = f"{plugin_id}:{contribution_id}"
        if key in self._contributions[extension_point]:
            raise ValueError(f"Contribution already registered: {key}")
        contribution = PluginContribution(
            plugin_id=plugin_id,
            extension_point=extension_point,
            contribution_id=contribution_id,
            handler=handler,
            metadata=dict(metadata or {}),
        )
        self._contributions[extension_point][key] = contribution
        return contribution

    def unregister_plugin(self, plugin_id: str) -> None:
        for contributions in self._contributions.values():
            for key in [
                key for key, value in contributions.items()
                if value.plugin_id == plugin_id
            ]:
                del contributions[key]
        self._grants.pop(plugin_id, None)

    def list_contributions(
        self, extension_point: ExtensionPoint
    ) -> list[PluginContribution]:
        return list(self._contributions[extension_point].values())

    def require(self, plugin_id: str, permission: PluginPermission) -> None:
        if permission not in self._grants.get(plugin_id, frozenset()):
            raise PluginPermissionError(
                f"Plugin '{plugin_id}' lacks permission '{permission.value}'."
            )

    def has_permission(self, plugin_id: str, permission: PluginPermission) -> bool:
        return permission in self._grants.get(plugin_id, frozenset())

class BoundExtensionAPI:
    """Plugin-scoped facade that prevents impersonating another plugin ID."""

    def __init__(self, api: ExtensionAPI, plugin_id: str) -> None:
        self._api = api
        self.plugin_id = plugin_id

    def register(
        self,
        extension_point: ExtensionPoint,
        contribution_id: str,
        handler: Callable[..., Any],
        metadata: dict[str, Any] | None = None,
    ) -> PluginContribution:
        return self._api.register(
            self.plugin_id, extension_point, contribution_id, handler, metadata
        )

    def require(self, permission: PluginPermission) -> None:
        self._api.require(self.plugin_id, permission)

    def has_permission(self, permission: PluginPermission) -> bool:
        return self._api.has_permission(self.plugin_id, permission)

extension_api = ExtensionAPI()
