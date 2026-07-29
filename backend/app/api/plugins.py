from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.security import Permission, Principal, audit_log, require_permission
from app.review.rule_engine.plugin import PluginManager


router = APIRouter(prefix="/api/plugins", tags=["plugins"])
plugin_manager = PluginManager([
    Path(__file__).resolve().parents[2] / "plugins",
])
plugin_manager.discover()


def _serialize(record) -> dict[str, Any]:
    return {
        "id": record.manifest.id,
        "name": record.manifest.name,
        "version": record.manifest.version,
        "type": record.manifest.plugin_type,
        "permissions": list(record.manifest.permissions),
        "state": record.state.value,
        "error": record.error,
        "checksum": record.checksum,
        "audit": list(record.audit),
    }


def _record(plugin_id: str):
    try:
        return plugin_manager.plugins[plugin_id]
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Plugin not installed.") from error


@router.get("")
def list_plugins(
    principal: Principal = Depends(require_permission(Permission.MANAGE_PLUGINS)),
) -> dict[str, Any]:
    records = plugin_manager.list_plugins()
    return {"total": len(records), "items": [_serialize(item) for item in records]}


@router.post("/{plugin_id}/validate")
def validate_plugin(
    plugin_id: str,
    principal: Principal = Depends(require_permission(Permission.MANAGE_PLUGINS)),
) -> dict[str, Any]:
    _record(plugin_id)
    errors = plugin_manager.validate(plugin_id)
    audit_log.record(actor_id=principal.user_id, action="plugin.validate", resource_type="plugin", resource_id=plugin_id, outcome="success" if not errors else "denied")
    return {"plugin_id": plugin_id, "valid": not errors, "errors": errors}


@router.post("/{plugin_id}/enable")
def enable_plugin(
    plugin_id: str,
    principal: Principal = Depends(require_permission(Permission.MANAGE_PLUGINS)),
) -> dict[str, Any]:
    record = _record(plugin_id)
    if not plugin_manager.enable(plugin_id):
        raise HTTPException(status_code=422, detail=record.error or "Plugin could not be enabled.")
    audit_log.record(actor_id=principal.user_id, action="plugin.enable", resource_type="plugin", resource_id=plugin_id)
    return _serialize(record)


@router.post("/{plugin_id}/disable")
def disable_plugin(
    plugin_id: str,
    principal: Principal = Depends(require_permission(Permission.MANAGE_PLUGINS)),
) -> dict[str, Any]:
    record = _record(plugin_id)
    plugin_manager.disable(plugin_id)
    audit_log.record(actor_id=principal.user_id, action="plugin.disable", resource_type="plugin", resource_id=plugin_id)
    return _serialize(record)
