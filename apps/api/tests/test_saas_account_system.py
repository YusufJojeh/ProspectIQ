from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.modules.billing.models import Subscription
from app.modules.billing.service import BillingService
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


def _seed_roles(db: Session) -> None:
    db.add_all(
        [
            Role(key="account_owner", label="Account Owner"),
            Role(key="admin", label="Administrator"),
            Role(key="manager", label="Manager"),
            Role(key="member", label="Member"),
        ]
    )
    db.commit()


def _create_workspace_with_users(
    db: Session,
    *,
    name: str,
    slug: str,
    owner_email: str,
    admin_email: str,
    manager_email: str,
) -> dict[str, str]:
    workspace = Workspace(name=name, slug=slug, status="active", settings_json={"locale": "en-US"})
    db.add(workspace)
    db.flush()

    owner = User(
        workspace_id=workspace.id,
        email=owner_email,
        full_name=f"{name} Owner",
        hashed_password=hash_password("OwnerPass123!"),
        role="account_owner",
        status="active",
    )
    admin = User(
        workspace_id=workspace.id,
        email=admin_email,
        full_name=f"{name} Admin",
        hashed_password=hash_password("AdminPass123!"),
        role="admin",
        status="active",
    )
    manager = User(
        workspace_id=workspace.id,
        email=manager_email,
        full_name=f"{name} Manager",
        hashed_password=hash_password("ManagerPass123!"),
        role="manager",
        status="active",
    )
    db.add_all([owner, admin, manager])
    db.flush()
    workspace.owner_user_id = owner.id
    db.add(workspace)
    db.commit()
    BillingService().ensure_seed_data(db)
    BillingService().bootstrap_workspace_subscription(db, workspace=workspace, actor_user_id=owner.id)
    return {
        "workspace_public_id": workspace.public_id,
        "owner_public_id": owner.public_id,
        "owner_email": owner.email,
        "admin_public_id": admin.public_id,
        "admin_email": admin.email,
        "manager_public_id": manager.public_id,
        "manager_email": manager.email,
    }


def _login(client: TestClient, *, email: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


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


def test_signup_bootstraps_workspace_owner_permissions_and_billing_state() -> None:
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
    assert "billing:manage" in payload["user"]["permissions"]
    assert "team:manage" in payload["user"]["permissions"]

    with session_factory() as db:
        workspace = db.scalar(select(Workspace).where(Workspace.slug == "northbeam-analytics"))
        assert workspace is not None
        owner = db.scalar(select(User).where(User.email == "avery@northbeam.com"))
        assert owner is not None
        assert workspace.owner_user_id == owner.id
        subscription = db.scalar(select(Subscription).where(Subscription.workspace_id == workspace.id))
        assert subscription is not None
        assert subscription.status == "trialing"


def test_workspace_isolation_blocks_cross_account_user_and_billing_access() -> None:
    session_factory = _build_session_factory()
    with session_factory() as db:
        _seed_roles(db)
        alpha = _create_workspace_with_users(
            db,
            name="Alpha",
            slug="alpha",
            owner_email="owner@alpha.com",
            admin_email="admin@alpha.com",
            manager_email="manager@alpha.com",
        )
        beta = _create_workspace_with_users(
            db,
            name="Beta",
            slug="beta",
            owner_email="owner@beta.com",
            admin_email="admin@beta.com",
            manager_email="manager@beta.com",
        )

    with _override_client(session_factory) as client:
        alpha_owner_token = _login(client, email="owner@alpha.com", password="OwnerPass123!")
        beta_owner_token = _login(client, email="owner@beta.com", password="OwnerPass123!")

        alpha_invoices = client.get(
            "/api/v1/billing/invoices",
            headers={"Authorization": f"Bearer {alpha_owner_token}"},
        )
        assert alpha_invoices.status_code == 200
        alpha_invoice_id = alpha_invoices.json()["items"][0]["public_id"]

        cross_user_response = client.get(
            f"/api/v1/users/{alpha['admin_public_id']}",
            headers={"Authorization": f"Bearer {beta_owner_token}"},
        )
        cross_invoice_response = client.post(
            "/api/v1/billing/invoices/mark-paid",
            headers={"Authorization": f"Bearer {beta_owner_token}"},
            json={"invoice_public_id": alpha_invoice_id},
        )

    assert cross_user_response.status_code == 404
    assert cross_invoice_response.status_code == 404


def test_team_management_respects_role_boundaries_inside_workspace() -> None:
    session_factory = _build_session_factory()
    with session_factory() as db:
        _seed_roles(db)
        seeded = _create_workspace_with_users(
            db,
            name="Gamma",
            slug="gamma",
            owner_email="owner@gamma.com",
            admin_email="admin@gamma.com",
            manager_email="manager@gamma.com",
        )

    with _override_client(session_factory) as client:
        owner_token = _login(client, email=seeded["owner_email"], password="OwnerPass123!")
        admin_token = _login(client, email=seeded["admin_email"], password="AdminPass123!")
        manager_token = _login(client, email=seeded["manager_email"], password="ManagerPass123!")

        upgrade_plan = client.post(
            "/api/v1/billing/subscription/change",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"plan_code": "growth", "billing_cycle": "monthly"},
        )
        assert upgrade_plan.status_code == 200

        owner_create = client.post(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "email": "member-one@gamma.com",
                "full_name": "Member One",
                "password": "MemberOnePass123!",
                "role": "member",
            },
        )
        admin_create = client.post(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "email": "member-two@gamma.com",
                "full_name": "Member Two",
                "password": "MemberTwoPass123!",
                "role": "member",
            },
        )
        manager_create = client.post(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {manager_token}"},
            json={
                "email": "blocked@gamma.com",
                "full_name": "Blocked User",
                "password": "BlockedPass123!",
                "role": "member",
            },
        )
        admin_promote_owner = client.patch(
            f"/api/v1/users/{seeded['manager_public_id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"role": "account_owner"},
        )

    assert owner_create.status_code == 201
    assert admin_create.status_code == 201
    assert manager_create.status_code == 403
    assert admin_promote_owner.status_code == 403


def test_simulated_billing_lifecycle_supports_change_failure_success_cancel_and_renew() -> None:
    session_factory = _build_session_factory()

    with _override_client(session_factory) as client:
        signup_response = client.post(
            "/api/v1/auth/signup",
            json={
                "full_name": "Billing Owner",
                "workspace_name": "Billing Works",
                "email": "owner@billing.com",
                "password": "BillingPass123!",
            },
        )
        assert signup_response.status_code == 200
        owner_token = signup_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {owner_token}"}

        change_response = client.post(
            "/api/v1/billing/subscription/change",
            headers=headers,
            json={"plan_code": "growth", "billing_cycle": "yearly"},
        )
        assert change_response.status_code == 200
        assert change_response.json()["plan_code"] == "growth"
        assert change_response.json()["billing_cycle"] == "yearly"

        invoices_response = client.get("/api/v1/billing/invoices", headers=headers)
        assert invoices_response.status_code == 200
        latest_invoice_id = invoices_response.json()["items"][0]["public_id"]

        failed_payment = client.post(
            "/api/v1/billing/invoices/simulate-failure",
            headers=headers,
            json={"invoice_public_id": latest_invoice_id, "error_message": "Simulated card decline."},
        )
        assert failed_payment.status_code == 200
        assert failed_payment.json()["status"] == "past_due"
        assert failed_payment.json()["payment_attempts"][0]["simulated_result"] == "failure"

        subscription_after_failure = client.get("/api/v1/billing/subscription", headers=headers)
        assert subscription_after_failure.status_code == 200
        assert subscription_after_failure.json()["status"] == "past_due"

        paid_invoice = client.post(
            "/api/v1/billing/invoices/mark-paid",
            headers=headers,
            json={"invoice_public_id": latest_invoice_id},
        )
        assert paid_invoice.status_code == 200
        assert paid_invoice.json()["status"] == "paid"
        assert paid_invoice.json()["payment_attempts"][0]["simulated_result"] == "success"

        canceled_subscription = client.post("/api/v1/billing/subscription/cancel", headers=headers)
        assert canceled_subscription.status_code == 200
        assert canceled_subscription.json()["status"] == "canceled"
        assert canceled_subscription.json()["ends_at"] is not None

        renewed_subscription = client.post("/api/v1/billing/subscription/renew", headers=headers)
        assert renewed_subscription.status_code == 200
        assert renewed_subscription.json()["status"] == "active"
        assert renewed_subscription.json()["ends_at"] is None

        invoices_after_renew = client.get("/api/v1/billing/invoices", headers=headers)
        assert invoices_after_renew.status_code == 200
        assert len(invoices_after_renew.json()["items"]) >= 3
