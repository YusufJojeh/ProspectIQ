from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.rate_limit import _windows
from app.core.security import hash_password
from app.main import app
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


def _seed(session_factory: sessionmaker[Session]) -> None:
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
            public_id="ws_rl",
            name="Rate Limit WS",
            slug=normalize_workspace_slug("Rate Limit WS"),
            settings_json={"locale": "en-US"},
        )
        db.add(workspace)
        db.commit()
        db.refresh(workspace)
        owner = User(
            workspace_id=workspace.id,
            email="rl@example.com",
            full_name="RL User",
            hashed_password=hash_password("RLPass123!"),
            role="account_owner",
            status="active",
        )
        db.add(owner)
        db.commit()
        db.refresh(owner)
        workspace.owner_user_id = owner.id
        db.add(workspace)
        db.commit()
        BillingService().ensure_seed_data(db)
        BillingService().bootstrap_workspace_subscription(
            db, workspace=workspace, actor_user_id=owner.id
        )


@contextmanager
def _override_client(session_factory: sessionmaker[Session]) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        with session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@contextmanager
def _rate_limit_enabled_ctx():
    """Enable the rate limiter for a specific test block."""
    import app.core.rate_limit as _rl

    _rl._windows.clear()
    _rl._enabled = True
    try:
        yield
    finally:
        _rl._enabled = False
        _rl._windows.clear()


def test_login_rate_limit_returns_429_after_limit() -> None:
    session_factory = _build_session_factory()
    _seed(session_factory)

    with _rate_limit_enabled_ctx(), _override_client(session_factory) as client:
        import time

        now = time.monotonic()
        scope_key = "auth:login:testclient"
        _windows[scope_key] = [now] * 10

        response = client.post(
            "/api/v1/auth/login",
            json={"email": "rl@example.com", "password": "RLPass123!"},
        )

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "auth.rate_limited"
    assert "Retry-After" in response.headers


def test_login_succeeds_within_rate_limit() -> None:
    session_factory = _build_session_factory()
    _seed(session_factory)

    # Rate limiter disabled by conftest; login should always succeed
    with _override_client(session_factory) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "rl@example.com", "password": "RLPass123!"},
        )

    assert response.status_code == 200
    assert "access_token" in response.json()


def test_signup_rate_limit_returns_429_after_limit() -> None:
    session_factory = _build_session_factory()
    _seed(session_factory)

    with _rate_limit_enabled_ctx(), _override_client(session_factory) as client:
        import time

        now = time.monotonic()
        scope_key = "auth:signup:testclient"
        _windows[scope_key] = [now] * 5

        response = client.post(
            "/api/v1/auth/signup",
            json={
                "full_name": "Rate Test",
                "workspace_name": "Rate WS Test",
                "email": "ratetest@example.com",
                "password": "RatePass123!",
            },
        )

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "auth.rate_limited"
