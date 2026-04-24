from __future__ import annotations

from typing import Literal

from app.core.errors import ForbiddenError

WorkspacePermission = Literal[
    "workspace:view",
    "workspace:manage",
    "team:view",
    "team:manage",
    "billing:view",
    "billing:manage",
    "admin:view",
    "admin:manage",
    "audit_logs:view",
    "searches:run",
    "leads:view",
    "leads:manage",
    "ai_analysis:run",
    "outreach:manage",
    "exports:run",
]

ROLE_PERMISSIONS: dict[str, tuple[WorkspacePermission, ...]] = {
    "account_owner": (
        "workspace:view",
        "workspace:manage",
        "team:view",
        "team:manage",
        "billing:view",
        "billing:manage",
        "admin:view",
        "admin:manage",
        "audit_logs:view",
        "searches:run",
        "leads:view",
        "leads:manage",
        "ai_analysis:run",
        "outreach:manage",
        "exports:run",
    ),
    "admin": (
        "workspace:view",
        "workspace:manage",
        "team:view",
        "team:manage",
        "billing:view",
        "admin:view",
        "admin:manage",
        "audit_logs:view",
        "searches:run",
        "leads:view",
        "leads:manage",
        "ai_analysis:run",
        "outreach:manage",
        "exports:run",
    ),
    "manager": (
        "workspace:view",
        "team:view",
        "searches:run",
        "leads:view",
        "leads:manage",
        "ai_analysis:run",
        "outreach:manage",
        "exports:run",
    ),
    "member": (
        "workspace:view",
        "team:view",
        "leads:view",
        "leads:manage",
        "ai_analysis:run",
        "outreach:manage",
        "exports:run",
    ),
}


def get_role_permissions(role: str) -> list[WorkspacePermission]:
    return list(ROLE_PERMISSIONS.get(role, ()))


def has_workspace_permission(role: str, permission: WorkspacePermission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, ())


def assert_workspace_permission(role: str, permission: WorkspacePermission, *, message: str) -> None:
    if not has_workspace_permission(role, permission):
        raise ForbiddenError(message)
