from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from .contracts import ExtensionAPI, PluginPermission, extension_api
from .events import PluginEventBus


class PluginLifecycle(str, Enum):
    INSTALLED = "installed"
    VALIDATED = "validated"
    LOADED = "loaded"
    INITIALIZED = "initialized"
    REGISTERED = "registered"
    ENABLED = "enabled"
    DISABLED = "disabled"
    UNLOADED = "unloaded"
    REMOVED = "removed"
    ERROR = "error"


@dataclass(frozen=True)
class ExtensionManifest:
    id: str
    name: str
    version: str
    api_version: str = "1"
    min_core_version: str = "1.0.0"
    max_core_version: str = ""
    plugin_type: str = "knowledge_pack"
    permissions: tuple[str, ...] = ()
    requires: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    entry_point: str = ""
    signature: str = ""
    description: str = ""


@dataclass
class ManagedPlugin:
    manifest: ExtensionManifest
    path: Path
    checksum: str
    state: PluginLifecycle = PluginLifecycle.INSTALLED
    module: Any = None
    error: str = ""
    audit: list[str] = field(default_factory=list)


class PluginManager:
    """Secure lifecycle manager for declarative or explicitly trusted plugins."""

    _ID_PATTERN = re.compile(r"^[a-z][a-z0-9._-]{2,80}$")
    _PLUGIN_TYPES = {
        "knowledge_pack", "rule", "ai", "export", "dashboard", "integration"
    }

    def __init__(
        self,
        plugin_dirs: list[Path] | None = None,
        *,
        core_version: str = "1.0.0",
        api_version: str = "1",
        allow_code_plugins: bool = False,
        signature_verifier: Callable[[Path, ExtensionManifest], bool] | None = None,
        api: ExtensionAPI | None = None,
    ) -> None:
        self.plugin_dirs = [Path(item) for item in (plugin_dirs or [])]
        self.core_version = core_version
        self.api_version = api_version
        self.allow_code_plugins = allow_code_plugins
        self.signature_verifier = signature_verifier
        self.api = api or extension_api
        self.plugins: dict[str, ManagedPlugin] = {}
        self.events = PluginEventBus(self.is_enabled)

    def discover(self) -> list[ManagedPlugin]:
        discovered: list[ManagedPlugin] = []
        for root in self.plugin_dirs:
            if not root.is_dir():
                continue
            for manifest_path in sorted(root.glob("*/plugin.json")):
                try:
                    record = self.install(manifest_path.parent)
                    discovered.append(record)
                except (OSError, ValueError, json.JSONDecodeError):
                    continue
        return discovered

    def install(self, plugin_path: Path) -> ManagedPlugin:
        """Install from an already-local directory; downloading is outside this layer."""
        resolved = Path(plugin_path).resolve()
        manifest_path = resolved / "plugin.json"
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest = self._parse_manifest(data)
        checksum = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        existing = self.plugins.get(manifest.id)
        if existing and existing.path != resolved:
            raise ValueError(f"Plugin ID already installed from another path: {manifest.id}")
        record = ManagedPlugin(manifest=manifest, path=resolved, checksum=checksum)
        record.audit.append("installed")
        self.plugins[manifest.id] = record
        return record

    def validate(self, plugin_id: str) -> list[str]:
        record = self._require(plugin_id)
        manifest = record.manifest
        errors: list[str] = []
        if not self._ID_PATTERN.fullmatch(manifest.id):
            errors.append("Invalid plugin id.")
        if manifest.plugin_type not in self._PLUGIN_TYPES:
            errors.append(f"Unsupported plugin type: {manifest.plugin_type}")
        if manifest.api_version != self.api_version:
            errors.append(
                f"Extension API {manifest.api_version} is incompatible with {self.api_version}."
            )
        if self._version(self.core_version) < self._version(manifest.min_core_version):
            errors.append(f"Requires ReviewMind >= {manifest.min_core_version}.")
        if (
            manifest.max_core_version
            and self._version(self.core_version) > self._version(manifest.max_core_version)
        ):
            errors.append(f"Requires ReviewMind <= {manifest.max_core_version}.")
        for dependency in manifest.requires:
            if dependency not in self.plugins:
                errors.append(f"Missing dependency: {dependency}")
        for conflict in manifest.conflicts:
            other = self.plugins.get(conflict)
            if other and other.state not in {
                PluginLifecycle.DISABLED, PluginLifecycle.UNLOADED, PluginLifecycle.REMOVED
            }:
                errors.append(f"Conflicts with installed plugin: {conflict}")
        for permission in manifest.permissions:
            try:
                PluginPermission(permission)
            except ValueError:
                errors.append(f"Unknown permission: {permission}")
        if manifest.entry_point:
            entry = (record.path / manifest.entry_point).resolve()
            if record.path not in entry.parents or not entry.is_file():
                errors.append("Entry point escapes plugin directory or does not exist.")
            if not self.allow_code_plugins:
                errors.append("Executable plugins are disabled.")
            elif not manifest.signature:
                errors.append("Executable plugin is unsigned.")
            elif not self.signature_verifier or not self.signature_verifier(record.path, manifest):
                errors.append("Plugin signature verification failed.")
        if errors:
            record.state = PluginLifecycle.ERROR
            record.error = "; ".join(errors)
        else:
            self.api.grant(manifest.id, list(manifest.permissions))
            record.state = PluginLifecycle.VALIDATED
            record.error = ""
            record.audit.append("validated")
        return errors

    def load(self, plugin_id: str) -> bool:
        record = self._require(plugin_id)
        if self.validate(plugin_id):
            return False
        if record.manifest.entry_point:
            entry = (record.path / record.manifest.entry_point).resolve()
            spec = importlib.util.spec_from_file_location(
                f"reviewmind_plugin_{plugin_id.replace('.', '_')}", entry
            )
            if not spec or not spec.loader:
                return self._fail(record, "Unable to load plugin entry point.")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            record.module = module
        record.state = PluginLifecycle.LOADED
        record.audit.append("loaded")
        return True

    def enable(self, plugin_id: str) -> bool:
        record = self._require(plugin_id)
        if record.state == PluginLifecycle.DISABLED:
            record.state = PluginLifecycle.ENABLED
            record.audit.append("enabled")
            return True
        if record.state not in {
            PluginLifecycle.LOADED,
            PluginLifecycle.INITIALIZED,
            PluginLifecycle.REGISTERED,
            PluginLifecycle.ENABLED,
        }:
            if not self.load(plugin_id):
                return False
        if record.state == PluginLifecycle.ENABLED:
            return True
        bound_api = self.api.for_plugin(plugin_id)
        if record.module and hasattr(record.module, "initialize"):
            record.module.initialize(bound_api)
        record.state = PluginLifecycle.INITIALIZED
        record.audit.append("initialized")
        if record.module and hasattr(record.module, "register"):
            record.module.register(bound_api, self.events)
        record.state = PluginLifecycle.REGISTERED
        record.audit.append("registered")
        record.state = PluginLifecycle.ENABLED
        record.audit.append("enabled")
        return True

    def disable(self, plugin_id: str) -> None:
        record = self._require(plugin_id)
        record.state = PluginLifecycle.DISABLED
        record.audit.append("disabled")

    def unload(self, plugin_id: str) -> None:
        record = self._require(plugin_id)
        self.api.unregister_plugin(plugin_id)
        self.events.unsubscribe_plugin(plugin_id)
        record.module = None
        record.state = PluginLifecycle.UNLOADED
        record.audit.append("unloaded")

    def remove(self, plugin_id: str) -> None:
        """Remove registry state only; files remain recoverable on disk."""
        record = self._require(plugin_id)
        self.unload(plugin_id)
        record.state = PluginLifecycle.REMOVED
        record.audit.append("removed")
        del self.plugins[plugin_id]

    def is_enabled(self, plugin_id: str) -> bool:
        record = self.plugins.get(plugin_id)
        return bool(record and record.state == PluginLifecycle.ENABLED)

    def list_plugins(self) -> list[ManagedPlugin]:
        return sorted(self.plugins.values(), key=lambda item: item.manifest.id)

    def _parse_manifest(self, data: dict[str, Any]) -> ExtensionManifest:
        if not data.get("id") or not data.get("version"):
            raise ValueError("Plugin manifest requires id and version.")
        return ExtensionManifest(
            id=str(data["id"]),
            name=str(data.get("name", data["id"])),
            version=str(data["version"]),
            api_version=str(data.get("api_version", "1")),
            min_core_version=str(data.get("min_core_version", "1.0.0")),
            max_core_version=str(data.get("max_core_version", "")),
            plugin_type=str(data.get("plugin_type", "knowledge_pack")),
            permissions=tuple(data.get("permissions", [])),
            requires=tuple(data.get("requires", [])),
            conflicts=tuple(data.get("conflicts", [])),
            entry_point=str(data.get("entry_point", "")),
            signature=str(data.get("signature", "")),
            description=str(data.get("description", "")),
        )

    def _require(self, plugin_id: str) -> ManagedPlugin:
        try:
            return self.plugins[plugin_id]
        except KeyError as error:
            raise KeyError(f"Plugin not installed: {plugin_id}") from error

    @staticmethod
    def _version(value: str) -> tuple[int, ...]:
        try:
            return tuple(int(part) for part in value.split("."))
        except ValueError:
            return (0,)

    @staticmethod
    def _fail(record: ManagedPlugin, error: str) -> bool:
        record.state = PluginLifecycle.ERROR
        record.error = error
        record.audit.append(f"error:{error}")
        return False


plugin_manager = PluginManager()
