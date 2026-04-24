from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
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


def _seed_workspace(session_factory: sessionmaker[Session]) -> None:
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
            public_id="ws_billing",
            name="Billing Workspace",
            slug=normalize_workspace_slug("Billing Workspace"),
            settings_json={"locale": "en-US"},
        )
        db.add(workspace)
        db.commit()
        db.refresh(workspace)
        owner = User(
            workspace_id=workspace.id,
            email="owner@billing.com",
            full_name="Billing Owner",
            hashed_password=hash_password("BillingPass123!"),
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


def _login(client: TestClient) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@billing.com", "password": "BillingPass123!"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_billing_simulation_endpoints_work() -> None:
    session_factory = _build_session_factory()
    _seed_workspace(session_factory)

    with _override_client(session_factory) as client:
        token = _login(client)
        headers = {"Authorization": f"Bearer {token}"}
        plans = client.get("/api/v1/billing/plans", headers=headers)
        subscription = client.get("/api/v1/billing/subscription", headers=headers)
        invoices = client.get("/api/v1/billing/invoices", headers=headers)
        usage = client.get("/api/v1/billing/usage", headers=headers)

        assert plans.status_code == 200
        assert subscription.status_code == 200
        assert invoices.status_code == 200
        assert usage.status_code == 200

        invoice_public_id = invoices.json()["items"][0]["public_id"]
        failure = client.post(
            "/api/v1/billing/invoices/simulate-failure",
            headers=headers,
            json={"invoice_public_id": invoice_public_id},
        )
        assert failure.status_code == 200
        assert failure.json()["status"] == "past_due"

        paid = client.post(
            "/api/v1/billing/invoices/mark-paid",
            headers=headers,
            json={"invoice_public_id": invoice_public_id},
        )
        assert paid.status_code == 200
        assert paid.json()["status"] == "paid"
