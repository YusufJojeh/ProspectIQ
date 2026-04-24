from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.core.security import hash_password
from app.modules.audit_logs.service import AuditLogService
from app.modules.auth.permissions import assert_workspace_permission, get_role_permissions
from app.modules.billing.service import BillingService
from app.modules.users.models import Role, User, Workspace
from app.modules.users.repository import UsersRepository
from app.modules.users.schemas import (
    UserCreateRequest,
    UserDetailResponse,
    UserListResponse,
    UserOption,
    UserPasswordResetRequest,
    UserProfile,
    UserRole,
    UserStatus,
    WorkspaceSettingsResponse,
    WorkspaceSettingsUpdateRequest,
)


ROLE_ORDER = {
    "account_owner": 4,
    "admin": 3,
    "manager": 2,
    "member": 1,
}


def normalize_workspace_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug[:120] or "workspace"


def ensure_password_strength(password: str) -> str:
    if len(password) < 12:
        raise ConflictError("Password must be at least 12 characters long.")
    checks = [
        any(char.islower() for char in password),
        any(char.isupper() for char in password),
        any(char.isdigit() for char in password),
        any(not char.isalnum() for char in password),
    ]
    if not all(checks):
        raise ConflictError(
            "Password must include uppercase, lowercase, numeric, and special characters."
        )
    return password


class UsersService:
    def __init__(self) -> None:
        self.repository = UsersRepository()
        self.audit_logs = AuditLogService()
        self.billing = BillingService()

    def get_profile(self, user: User) -> UserProfile:
        return UserProfile(
            public_id=user.public_id,
            workspace_public_id=user.workspace.public_id,
            workspace_name=user.workspace.name,
            workspace_slug=user.workspace.slug,
            email=user.email,
            full_name=user.full_name,
            role=cast(UserRole, user.role),
            status=cast(UserStatus, user.status),
            avatar_url=user.avatar_url,
            job_title=user.job_title,
            permissions=get_role_permissions(user.role),
        )

    def list_workspace_users(self, db: Session, workspace_id: int) -> UserListResponse:
        users = self.repository.list_for_workspace(db, workspace_id)
        return UserListResponse(items=[self._to_option(item) for item in users])

    def get_workspace_user(self, db: Session, *, workspace_id: int, user_public_id: str) -> UserDetailResponse:
        user = self.repository.get_by_public_id(db, workspace_id, user_public_id)
        if user is None:
            raise NotFoundError("User was not found.")
        inviter_public_id = None
        if user.invited_by_user_id:
            inviter = db.get(User, user.invited_by_user_id)
            inviter_public_id = inviter.public_id if inviter else None
        return UserDetailResponse(
            **self._to_option(user).model_dump(),
            workspace_public_id=user.workspace.public_id,
            invited_by_user_public_id=inviter_public_id,
            avatar_url=user.avatar_url,
            updated_at=user.updated_at,
        )

    def create_workspace_user(
        self,
        db: Session,
        *,
        workspace_id: int,
        payload: UserCreateRequest,
        actor: User,
    ) -> UserOption:
        self._assert_team_manager(actor)
        self.billing.enforce_usage(
            db,
            workspace_id=workspace_id,
            metric_key="max_team_users",
            actor_user_id=actor.id,
        )
        email = payload.email.lower()
        ensure_password_strength(payload.password)
        existing = self.repository.get_by_email(db, email)
        if existing is not None:
            raise ConflictError("A user with that email already exists.")

        created = self.repository.add(
            db,
            User(
                workspace_id=workspace_id,
                email=email,
                full_name=payload.full_name.strip(),
                hashed_password=hash_password(payload.password),
                role=payload.role,
                status="active",
                invited_by_user_id=actor.id,
                job_title=payload.job_title,
                avatar_url=payload.avatar_url,
            ),
        )
        self.audit_logs.record(
            db,
            workspace_id=workspace_id,
            actor_user_id=actor.id,
            event_name="user.created",
            details=f"Created user {created.public_id} with role {created.role}.",
        )
        return self._to_option(created)

    def update_user(
        self,
        db: Session,
        *,
        workspace_id: int,
        user_public_id: str,
        payload,
        actor: User,
    ) -> UserDetailResponse:
        from app.modules.users.schemas import UserUpdateRequest

        payload = cast(UserUpdateRequest, payload)
        self._assert_team_manager(actor)
        user = self.repository.get_by_public_id(db, workspace_id, user_public_id)
        if user is None:
            raise NotFoundError("User was not found.")
        self._assert_manageable_target(actor, user)

        events: list[str] = []
        if payload.full_name is not None:
            user.full_name = payload.full_name.strip()
        if payload.job_title is not None:
            user.job_title = payload.job_title
        if payload.avatar_url is not None:
            user.avatar_url = payload.avatar_url
        if payload.status is not None and payload.status != user.status:
            user.status = payload.status
            events.append(f"status={payload.status}")
        if payload.role is not None and payload.role != user.role:
            self._assert_role_assignment(actor, current_role=user.role, next_role=payload.role)
            user.role = payload.role
            events.append(f"role={payload.role}")
        user.updated_at = datetime.now(tz=UTC)
        self.repository.save(db, user)
        if events:
            self.audit_logs.record(
                db,
                workspace_id=workspace_id,
                actor_user_id=actor.id,
                event_name="user.updated",
                details=f"Updated user {user.public_id}: {', '.join(events)}.",
            )
        return self.get_workspace_user(db, workspace_id=workspace_id, user_public_id=user.public_id)

    def reset_password(
        self,
        db: Session,
        *,
        workspace_id: int,
        user_public_id: str,
        payload: UserPasswordResetRequest,
        actor: User,
    ) -> UserDetailResponse:
        self._assert_team_manager(actor)
        ensure_password_strength(payload.password)
        user = self.repository.get_by_public_id(db, workspace_id, user_public_id)
        if user is None:
            raise NotFoundError("User was not found.")
        self._assert_manageable_target(actor, user)
        user.hashed_password = hash_password(payload.password)
        user.updated_at = datetime.now(tz=UTC)
        self.repository.save(db, user)
        self.audit_logs.record(
            db,
            workspace_id=workspace_id,
            actor_user_id=actor.id,
            event_name="user.password_reset",
            details=f"Reset password for user {user.public_id}.",
        )
        return self.get_workspace_user(db, workspace_id=workspace_id, user_public_id=user.public_id)

    def get_workspace_settings(self, db: Session, *, actor: User) -> WorkspaceSettingsResponse:
        workspace = actor.workspace
        owner_public_id = None
        if workspace.owner_user_id:
            owner = db.get(User, workspace.owner_user_id)
            owner_public_id = owner.public_id if owner else None
        return WorkspaceSettingsResponse(
            workspace=workspace,
            owner_user_public_id=owner_public_id,
            settings=cast(dict[str, object], workspace.settings_json or {}),
        )

    def update_workspace_settings(
        self,
        db: Session,
        *,
        actor: User,
        payload: WorkspaceSettingsUpdateRequest,
    ) -> WorkspaceSettingsResponse:
        if actor.role not in {"account_owner", "admin"}:
            raise ForbiddenError("Only workspace administrators can update workspace settings.")
        workspace = actor.workspace
        if payload.name is not None:
            workspace.name = payload.name.strip()
        if payload.slug is not None:
            slug = normalize_workspace_slug(payload.slug)
            existing = self.repository.get_workspace_by_slug(db, slug)
            if existing is not None and existing.id != workspace.id:
                raise ConflictError("Workspace slug is already in use.")
            workspace.slug = slug
        if payload.settings is not None:
            workspace.settings_json = payload.settings
        workspace.updated_at = datetime.now(tz=UTC)
        self.repository.save_workspace(db, workspace)
        self.audit_logs.record(
            db,
            workspace_id=workspace.id,
            actor_user_id=actor.id,
            event_name="workspace.updated",
            details=f"Updated workspace {workspace.public_id} settings.",
        )
        return self.get_workspace_settings(db, actor=actor)

    def _to_option(self, user: User) -> UserOption:
        return UserOption(
            public_id=user.public_id,
            email=user.email,
            full_name=user.full_name,
            role=cast(UserRole, user.role),
            status=cast(UserStatus, user.status),
            job_title=user.job_title,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
        )

    def _assert_team_manager(self, actor: User) -> None:
        assert_workspace_permission(
            actor.role,
            "team:manage",
            message="Only workspace owners and admins can manage team users.",
        )

    def _assert_manageable_target(self, actor: User, target: User) -> None:
        if actor.workspace_id != target.workspace_id:
            raise ForbiddenError("Cross-workspace user management is not allowed.")
        if target.role == "account_owner" and actor.role != "account_owner":
            raise ForbiddenError("Only the account owner can manage the account owner user.")
        if actor.id == target.id and target.role == "account_owner":
            return
        if ROLE_ORDER[actor.role] < ROLE_ORDER[target.role]:
            raise ForbiddenError("You cannot manage a user with a higher role.")

    def _assert_role_assignment(self, actor: User, *, current_role: str, next_role: str) -> None:
        if next_role == "account_owner" and actor.role != "account_owner":
            raise ForbiddenError("Only the account owner can assign the account owner role.")
        if current_role == "account_owner" and actor.role != "account_owner":
            raise ForbiddenError("Only the account owner can change the owner role.")
        if ROLE_ORDER[actor.role] < ROLE_ORDER[next_role]:
            raise ForbiddenError("You cannot assign a role higher than your own.")


def ensure_default_roles(db: Session) -> None:
    expected_roles = {
        "account_owner": ("Account Owner", "Full ownership of the workspace and billing."),
        "admin": ("Administrator", "Administrative workspace access."),
        "manager": ("Manager", "Operational product access with limited governance."),
        "member": ("Member", "Standard workspace access."),
    }
    existing = {key for key in db.scalars(select(Role.key).where(Role.key.in_(expected_roles)))}
    missing = [
        Role(key=key, label=label, description=description)
        for key, (label, description) in expected_roles.items()
        if key not in existing
    ]
    if missing:
        db.add_all(missing)
        db.commit()


def seed_default_workspace_and_admin(db: Session) -> tuple[Workspace, User]:
    settings = get_settings()
    repository = UsersRepository()
    ensure_default_roles(db)

    workspace = repository.get_workspace_by_public_id(db, settings.default_workspace_public_id)
    if workspace is None:
        workspace = repository.add_workspace(
            db,
            Workspace(
                public_id=settings.default_workspace_public_id,
                name=settings.default_workspace_name,
                slug=normalize_workspace_slug(settings.default_workspace_name),
                settings_json={"locale": "en-US"},
            ),
        )

    user = repository.get_by_email(db, settings.default_admin_email)
    if user is None:
        user = repository.add(
            db,
            User(
                workspace_id=workspace.id,
                email=settings.default_admin_email,
                full_name=settings.default_admin_name,
                hashed_password=hash_password(settings.default_admin_password),
                role="account_owner",
                status="active",
            ),
        )
    if workspace.owner_user_id != user.id:
        workspace.owner_user_id = user.id
        workspace.updated_at = datetime.now(tz=UTC)
        repository.save_workspace(db, workspace)
    return workspace, user
