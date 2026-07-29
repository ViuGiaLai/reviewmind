"""Plugin system for Rule Engine and Knowledge Packs.

Plugin lifecycle: DISCOVERED → VALIDATED → LOADED → ENABLED → DISABLED → UNLOADED
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


class PluginState(str, Enum):
    DISCOVERED = "discovered"
    VALIDATED = "validated"
    LOADED = "loaded"
    ENABLED = "enabled"
    DISABLED = "disabled"
    UNLOADED = "unloaded"
    ERROR = "error"


@dataclass(frozen=True)
class PluginManifest:
    """Plugin manifest describing a knowledge pack plugin."""
    id: str
    name: str
    version: str
    description: str = ""
    author: str = ""
    website: str = ""
    min_core_version: str = "1.0.0"
    max_core_version: str = ""
    requires: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    entry_point: str = ""
    config_schema: dict[str, Any] = field(default_factory=dict)


@dataclass
class PluginInstance:
    """A loaded plugin instance."""
    manifest: PluginManifest
    state: PluginState = PluginState.DISCOVERED
    path: Path = Path("")
    module: Any = None
    config: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    checksum: str = ""
    load_time: float = 0.0


class PluginRegistry:
    """Central registry for plugins with lifecycle management."""

    def __init__(self, plugin_dirs: list[Path] | None = None):
        self._plugins: dict[str, PluginInstance] = {}
        self._hooks: dict[str, list[Callable]] = {}
        self._plugin_dirs = plugin_dirs or []

    # ── Discovery ──────────────────────────────────────────────────────────

    def discover(self, directory: Path | None = None) -> list[PluginManifest]:
        """Discover plugins from a directory. Returns manifests found."""
        dirs = [directory] if directory else self._plugin_dirs
        manifests: list[PluginManifest] = []

        for plugin_dir in dirs:
            if not plugin_dir.is_dir():
                continue
            # Look for plugin.json or plugin.yaml manifest files
            for manifest_file in plugin_dir.glob("*/plugin.json"):
                try:
                    manifest = self._load_manifest(manifest_file)
                    manifests.append(manifest)
                    plugin_id = manifest.id
                    if plugin_id not in self._plugins:
                        checksum = hashlib.md5(
                            manifest_file.read_bytes()
                        ).hexdigest()
                        self._plugins[plugin_id] = PluginInstance(
                            manifest=manifest,
                            state=PluginState.DISCOVERED,
                            path=manifest_file.parent,
                            checksum=checksum,
                        )
                        logger.info(f"Discovered plugin: {plugin_id} v{manifest.version}")
                except Exception as e:
                    logger.warning(f"Failed to load manifest {manifest_file}: {e}")

        return manifests

    def add_plugin_dir(self, directory: Path) -> None:
        """Add a directory to search for plugins."""
        if directory not in self._plugin_dirs:
            self._plugin_dirs.append(directory)

    # ── Loading ────────────────────────────────────────────────────────────

    def load(self, plugin_id: str) -> bool:
        """Load a plugin from its manifest and entry point."""
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            logger.warning(f"Plugin '{plugin_id}' not found")
            return False

        if plugin.state in (PluginState.LOADED, PluginState.ENABLED):
            logger.info(f"Plugin '{plugin_id}' already loaded")
            return True

        try:
            # Validate first
            warnings = self.validate(plugin_id)
            if warnings:
                logger.warning(f"Plugin '{plugin_id}' validation warnings: {warnings}")

            # Load entry point if specified
            if plugin.manifest.entry_point:
                entry_path = plugin.path / plugin.manifest.entry_point
                if entry_path.is_file():
                    spec = importlib.util.spec_from_file_location(
                        f"plugin_{plugin_id}", entry_path
                    )
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        plugin.module = module
                        logger.info(f"Loaded plugin module: {plugin_id}")

            plugin.state = PluginState.LOADED
            import time
            plugin.load_time = time.time()
            self._trigger_hook("on_loaded", plugin_id)
            return True

        except Exception as e:
            plugin.state = PluginState.ERROR
            plugin.error = str(e)[:500]
            logger.error(f"Failed to load plugin '{plugin_id}': {e}")
            return False

    def enable(self, plugin_id: str) -> bool:
        """Enable a loaded plugin."""
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            return False
        if plugin.state == PluginState.ERROR:
            logger.warning(f"Cannot enable plugin '{plugin_id}' in error state")
            return False
        if plugin.state == PluginState.DISCOVERED:
            if not self.load(plugin_id):
                return False
        plugin.state = PluginState.ENABLED
        self._trigger_hook("on_enabled", plugin_id)
        return True

    def disable(self, plugin_id: str) -> None:
        """Disable an enabled plugin."""
        plugin = self._plugins.get(plugin_id)
        if plugin and plugin.state == PluginState.ENABLED:
            plugin.state = PluginState.DISABLED
            self._trigger_hook("on_disabled", plugin_id)

    def unload(self, plugin_id: str) -> None:
        """Unload a plugin completely."""
        plugin = self._plugins.get(plugin_id)
        if plugin:
            plugin.state = PluginState.UNLOADED
            plugin.module = None
            self._trigger_hook("on_unloaded", plugin_id)

    # ── Validation ─────────────────────────────────────────────────────────

    def validate(self, plugin_id: str) -> list[str]:
        """Validate plugin compatibility. Returns warnings list."""
        warnings: list[str] = []
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            warnings.append(f"Plugin '{plugin_id}' not found")
            return warnings

        manifest = plugin.manifest

        # Check dependencies
        for req in manifest.requires:
            dep = self._plugins.get(req)
            if not dep:
                warnings.append(f"Required plugin '{req}' not found")
            elif dep.state not in (PluginState.LOADED, PluginState.ENABLED):
                warnings.append(f"Required plugin '{req}' is not loaded")

        # Check conflicts
        for conflict in manifest.conflicts:
            if conflict in self._plugins:
                dep = self._plugins[conflict]
                if dep.state in (PluginState.LOADED, PluginState.ENABLED):
                    warnings.append(f"Plugin '{plugin_id}' conflicts with '{conflict}'")

        # Check version constraints (simplified)
        if manifest.min_core_version:
            try:
                min_parts = [int(x) for x in manifest.min_core_version.split(".")]
                # Placeholder: compare with actual core version
            except (ValueError, IndexError):
                warnings.append(f"Invalid min_core_version: {manifest.min_core_version}")

        return warnings

    def validate_dependencies(self, plugin_ids: list[str]) -> list[str]:
        """Validate a set of plugins for mutual compatibility."""
        warnings: list[str] = []
        selected = set(plugin_ids)

        for pid in plugin_ids:
            plugin = self._plugins.get(pid)
            if not plugin:
                warnings.append(f"Plugin '{pid}' not found")
                continue
            for req in plugin.manifest.requires:
                if req not in selected:
                    warnings.append(f"Plugin '{pid}' requires '{req}' (not selected)")
            for conflict in plugin.manifest.conflicts:
                if conflict in selected:
                    warnings.append(f"Plugin '{pid}' conflicts with '{conflict}'")

        return warnings

    # ── Query ──────────────────────────────────────────────────────────────

    def get(self, plugin_id: str) -> PluginInstance | None:
        return self._plugins.get(plugin_id)

    def list_plugins(
        self,
        state: PluginState | None = None,
        category: str | None = None,
    ) -> list[PluginInstance]:
        """List plugins with optional filtering."""
        results = list(self._plugins.values())
        if state:
            results = [p for p in results if p.state == state]
        if category:
            results = [p for p in results if category in p.manifest.categories]
        return sorted(results, key=lambda p: p.manifest.id)

    def get_by_category(self, category: str) -> list[PluginInstance]:
        """Get all plugins in a category."""
        return self.list_plugins(category=category)

    # ── Hooks ──────────────────────────────────────────────────────────────

    def on(self, event: str, callback: Callable) -> None:
        """Register a lifecycle hook callback."""
        self._hooks.setdefault(event, []).append(callback)

    def _trigger_hook(self, event: str, plugin_id: str) -> None:
        """Trigger lifecycle hooks."""
        for callback in self._hooks.get(event, []):
            try:
                callback(plugin_id)
            except Exception as e:
                logger.warning(f"Hook '{event}' failed for '{plugin_id}': {e}")

    # ── Persistence ────────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Serialize plugin states to dict for persistence."""
        return {
            pid: {
                "id": p.manifest.id,
                "name": p.manifest.name,
                "version": p.manifest.version,
                "state": p.state.value,
                "error": p.error,
                "load_time": p.load_time,
            }
            for pid, p in self._plugins.items()
        }

    # ── Internal ───────────────────────────────────────────────────────────

    def _load_manifest(self, manifest_file: Path) -> PluginManifest:
        """Parse a plugin.json manifest file."""
        data = json.loads(manifest_file.read_text(encoding="utf-8"))
        return PluginManifest(
            id=data["id"],
            name=data.get("name", data["id"]),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            website=data.get("website", ""),
            min_core_version=data.get("min_core_version", "1.0.0"),
            max_core_version=data.get("max_core_version", ""),
            requires=data.get("requires", []),
            conflicts=data.get("conflicts", []),
            categories=data.get("categories", []),
            entry_point=data.get("entry_point", ""),
            config_schema=data.get("config_schema", {}),
        )


# Global plugin registry
plugin_registry = PluginRegistry()
