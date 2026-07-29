from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from fastapi import HTTPException, Request, status


class Role(str, Enum):
    ADMINISTRATOR = "administrator"
    REVIEWER = "reviewer"
    EDITOR = "editor"
    VIEWER = "viewer"
    PLUGIN_DEVELOPER = "plugin_developer"


class Permission(str, Enum):
    REVIEW_DOCUMENT = "review_document"
    VIEW_DOCUMENT = "view_document"
    EDIT_DOCUMENT = "edit_document"
    APPLY_AUTOFIX = "apply_autofix"
    EXPORT_REPORT = "export_report"
    MANAGE_PLUGINS = "manage_plugins"
    VIEW_AUDIT = "view_audit"
    MANAGE_SECURITY = "manage_security"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMINISTRATOR: frozenset(Permission),
    Role.REVIEWER: frozenset({
        Permission.REVIEW_DOCUMENT, Permission.VIEW_DOCUMENT, Permission.EXPORT_REPORT,
    }),
    Role.EDITOR: frozenset({
        Permission.REVIEW_DOCUMENT, Permission.VIEW_DOCUMENT, Permission.EDIT_DOCUMENT,
        Permission.APPLY_AUTOFIX, Permission.EXPORT_REPORT,
    }),
    Role.VIEWER: frozenset({Permission.VIEW_DOCUMENT}),
    Role.PLUGIN_DEVELOPER: frozenset({
        Permission.VIEW_DOCUMENT, Permission.MANAGE_PLUGINS,
    }),
}


@dataclass(frozen=True)
class Principal:
    user_id: str
    role: Role

    def can(self, permission: Permission) -> bool:
        return permission in ROLE_PERMISSIONS[self.role]


def normalize_role(value: str) -> Role:
    aliases = {"admin": Role.ADMINISTRATOR, "user": Role.EDITOR}
    try:
        return aliases.get(value, Role(value))
    except ValueError:
        return Role.VIEWER


def require_permission(permission: Permission) -> Callable:
    async def dependency(request: Request) -> Principal:
        from app.api.auth import verify_clerk_session

        session = await verify_clerk_session(request)
        principal = Principal(
            user_id=session["user_id"],
            role=normalize_role(session.get("role", "viewer")),
        )
        if not principal.can(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission required: {permission.value}",
            )
        return principal

    return dependency
