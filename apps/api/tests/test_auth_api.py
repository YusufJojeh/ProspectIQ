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
from app.modules.users.models import Role, User, Workspace


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
                Role(key="admin", label="Administrator"),
                Role(key="agency_manager", label="Agency Manager"),
                Role(key="sales_user", label="Sales User"),
            ]
        )
        db.commit()

        workspace = Workspace(public_id="ws_test", name="Test Workspace")
        db.add(workspace)
        db.commit()
        db.refresh(workspace)

        users = {
            "admin": User(
                workspace_id=workspace.id,
                email="admin@example.com",
                full_name="Admin User",
                hashed_password=hash_password("AdminPass123"),
                role="admin",
            ),
            "manager": User(
                workspace_id=workspace.id,
                email="manager@example.com",
                full_name="Manager User",
                hashed_password=hash_password("ManagerPass123"),
                role="agency_manager",
            ),
            "sales": User(
                workspace_id=workspace.id,
                email="sales@example.com",
                full_name="Sales User",
                hashed_password=hash_password("SalesPass123"),
                role="sales_user",
            ),
        }
        db.add_all(users.values())
        db.commit()
        return {"workspace_public_id": workspace.public_id}


def _login(client: TestClient, *, email: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"workspace": "ws_test", "email": email, "password": password},
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
            json={
                "workspace": "ws_test",
                "email": "admin@example.com",
                "password": "AdminPass123",
            },
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
            json={
                "workspace": "ws_test",
                "email": "admin@example.com",
                "password": "wrong-password",
            },
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_protected_route_requires_bearer_token() -> None:
    session_factory = _build_session_factory()
    _seed_users(session_factory)

    with _override_client(session_factory) as client:
        response = client.get("/api/v1/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_role_restrictions_and_admin_user_creation() -> None:
    session_factory = _build_session_factory()
    _seed_users(session_factory)

    with _override_client(session_factory) as client:
        manager_token = _login(client, email="manager@example.com", password="ManagerPass123")
        sales_token = _login(client, email="sales@example.com", password="SalesPass123")
        admin_token = _login(client, email="admin@example.com", password="AdminPass123")

        manager_users_response = client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        sales_users_response = client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {sales_token}"},
        )
        sales_admin_response = client.get(
            "/api/v1/admin/provider-settings",
            headers={"Authorization": f"Bearer {sales_token}"},
        )
        create_user_response = client.post(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "email": "new-user@example.com",
                "full_name": "New User",
                "password": "NewUserPass123",
                "role": "sales_user",
            },
        )

    assert manager_users_response.status_code == 200
    assert len(manager_users_response.json()["items"]) == 3
    assert sales_users_response.status_code == 403
    assert sales_admin_response.status_code == 403
    assert create_user_response.status_code == 201
    assert create_user_response.json()["role"] == "sales_user"

    with session_factory() as db:
        assert (
            db.scalar(select(func.count(User.id)).where(User.email == "new-user@example.com")) == 1
        )
        assert (
            db.scalar(select(func.count(AuditLog.id)).where(AuditLog.event_name == "user.created"))
            == 1
        )
