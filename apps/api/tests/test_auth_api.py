from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.modules.audit_logs.models import AuditLog
from app.modules.billing.service import BillingService
from app.modules.users.models import Role, User, Workspace
from app.modules.users.service import normalize_workspace_slug


def _build_session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )


def _seed_users(session_factory: sessionmaker[Session]) -> dict[str, str]:
    with session_factory() as db:
        db.add_all(
            [
                Role(key="account_owner", label="Account Owner"),
                Role(key="admin", label="Administrator"),
                Role(key="manager", label="Manager"),
                Role(key="member", label="Member"),
            ]
        )
        db.commit()

        workspace = Workspace(
            public_id="ws_test",
            name="Test Workspace",
            slug=normalize_workspace_slug("Test Workspace"),
            settings_json={"locale": "en-US"},
        )
        db.add(workspace)
        db.commit()
        db.refresh(workspace)

        users = {
            "owner": User(
                workspace_id=workspace.id,
                email="owner@example.com",
                full_name="Owner User",
                hashed_password=hash_password("OwnerPass123!"),
                role="account_owner",
                status="active",
            ),
            "admin": User(
                workspace_id=workspace.id,
                email="admin@example.com",
                full_name="Admin User",
                hashed_password=hash_password("AdminPass123!"),
                role="admin",
                status="active",
            ),
            "manager": User(
                workspace_id=workspace.id,
                email="manager@example.com",
                full_name="Manager User",
                hashed_password=hash_password("ManagerPass123!"),
                role="manager",
                status="active",
            ),
            "member": User(
                workspace_id=workspace.id,
                email="member@example.com",
                full_name="Member User",
                hashed_password=hash_password("MemberPass123!"),
                role="member",
                status="active",
            ),
        }
        db.add_all(users.values())
        db.commit()
        workspace.owner_user_id = users["owner"].id
        db.add(workspace)
        db.commit()
        BillingService().ensure_seed_data(db)
        subscription = BillingService().bootstrap_workspace_subscription(
            db, workspace=workspace, actor_user_id=users["owner"].id
        )
        growth_plan = BillingService().repository.get_plan_by_code(db, "growth")
        assert growth_plan is not None
        subscription.plan_id = growth_plan.id
        db.add(subscription)
        db.commit()
        return {"workspace_public_id": workspace.public_id}


def _login(client: TestClient, *, email: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@contextmanager
def _override_client(
    session_factory: sessionmaker[Session],
) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        with session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def test_login_success_records_audit_log() -> None:
    session_factory = _build_session_factory()
    _seed_users(session_factory)

    with _override_client(session_factory) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.com", "password": "AdminPass123!"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["role"] == "admin"
    assert payload["token_type"] == "bearer"

    with session_factory() as db:
        assert (
            db.scalar(select(func.count(AuditLog.id)).where(AuditLog.event_name == "auth.login"))
            == 1
        )


def test_login_invalid_credentials_returns_unauthorized() -> None:
    session_factory = _build_session_factory()
    _seed_users(session_factory)

    with _override_client(session_factory) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.com", "password": "WrongPass123!"},
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_protected_route_requires_bearer_token() -> None:
    session_factory = _build_session_factory()
    _seed_users(session_factory)

    with _override_client(session_factory) as client:
        response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_member_can_export_leads_csv() -> None:
    session_factory = _build_session_factory()
    _seed_users(session_factory)

    with _override_client(session_factory) as client:
        token = _login(client, email="member@example.com", password="MemberPass123!")
        response = client.get(
            "/api/v1/exports/leads.csv",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert "text/csv" in response.headers.get("content-type", "")


def test_role_restrictions_and_admin_user_creation() -> None:
    session_factory = _build_session_factory()
    _seed_users(session_factory)

    with _override_client(session_factory) as client:
        admin_token = _login(client, email="admin@example.com", password="AdminPass123!")
        manager_token = _login(client, email="manager@example.com", password="ManagerPass123!")

        admin_list_response = client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        manager_create_response = client.post(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {manager_token}"},
            json={
                "email": "blocked@example.com",
                "full_name": "Blocked User",
                "password": "BlockedPass123!",
                "role": "member",
            },
        )
        create_user_response = client.post(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "email": "new-user@example.com",
                "full_name": "New User",
                "password": "NewUserPass123!",
                "role": "member",
            },
        )

    assert admin_list_response.status_code == 200
    assert len(admin_list_response.json()["items"]) == 4
    assert manager_create_response.status_code == 403
    assert create_user_response.status_code == 201
    assert create_user_response.json()["role"] == "member"

    with session_factory() as db:
        assert (
            db.scalar(select(func.count(User.id)).where(User.email == "new-user@example.com")) == 1
        )
        assert (
            db.scalar(select(func.count(AuditLog.id)).where(AuditLog.event_name == "user.created"))
            == 1
        )


def test_signup_creates_workspace_owner_and_subscription() -> None:
    session_factory = _build_session_factory()

    with _override_client(session_factory) as client:
        response = client.post(
            "/api/v1/auth/signup",
            json={
                "full_name": "Avery North",
                "workspace_name": "Northbeam Analytics",
                "email": "avery@northbeam.com",
                "password": "NorthbeamPass123!",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["role"] == "account_owner"
    assert payload["user"]["workspace_slug"] == "northbeam-analytics"
