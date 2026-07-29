import json

import pytest

from app.review.rule_engine.plugin import (
    ExtensionAPI,
    ExtensionPoint,
    PluginLifecycle,
    PluginManager,
    PluginPermissionError,
)


def _write_manifest(tmp_path, plugin_id="sample.rules", **overrides):
    directory = tmp_path / plugin_id
    directory.mkdir()
    manifest = {
        "id": plugin_id,
        "name": "Sample",
        "version": "1.0.0",
        "api_version": "1",
        "plugin_type": "rule",
        "permissions": ["add_rule"],
    }
    manifest.update(overrides)
    (directory / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")
    return directory


def test_declarative_plugin_lifecycle_permissions_and_events(tmp_path) -> None:
    plugin_dir = _write_manifest(tmp_path)
    api = ExtensionAPI()
    manager = PluginManager([tmp_path], api=api)
    manager.discover()

    assert manager.validate("sample.rules") == []
    assert manager.enable("sample.rules")
    assert manager.plugins["sample.rules"].state == PluginLifecycle.ENABLED

    contribution = api.for_plugin("sample.rules").register(
        ExtensionPoint.RULE,
        "sample-rule",
        lambda document: [],
    )
    assert contribution.plugin_id == "sample.rules"

    received = []
    manager.events.subscribe("sample.rules", "issues.generated", received.append)
    manager.events.publish("issues.generated", {"count": 2})
    assert received[0].payload["count"] == 2

    manager.disable("sample.rules")
    manager.events.publish("issues.generated", {"count": 3})
    assert len(received) == 1


def test_extension_api_denies_undeclared_capability(tmp_path) -> None:
    _write_manifest(tmp_path)
    api = ExtensionAPI()
    manager = PluginManager([tmp_path], api=api)
    manager.discover()
    assert manager.enable("sample.rules")

    with pytest.raises(PluginPermissionError):
        api.for_plugin("sample.rules").register(
            ExtensionPoint.EXPORTER,
            "secret-export",
            lambda document: document,
        )


def test_executable_plugin_is_denied_by_default(tmp_path) -> None:
    plugin_dir = _write_manifest(
        tmp_path,
        entry_point="plugin.py",
        signature="claimed-signature",
    )
    (plugin_dir / "plugin.py").write_text("VALUE = 1\n", encoding="utf-8")
    manager = PluginManager([tmp_path])
    manager.discover()

    errors = manager.validate("sample.rules")
    assert "Executable plugins are disabled." in errors
    assert not manager.enable("sample.rules")
    assert manager.plugins["sample.rules"].state == PluginLifecycle.ERROR


def test_unknown_permission_never_receives_a_grant(tmp_path) -> None:
    _write_manifest(tmp_path, permissions=["access_database"])
    api = ExtensionAPI()
    manager = PluginManager([tmp_path], api=api)
    manager.discover()

    errors = manager.validate("sample.rules")
    assert any("Unknown permission" in error for error in errors)
    assert not api._grants
