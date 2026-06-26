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
from app.modules.ai_analysis.models import AIAnalysisSnapshot, AIFeedback, PromptTemplate
from app.modules.audit_logs.models import AuditLog
from app.modules.billing.models import (
    Invoice,
    InvoiceItem,
    PaymentAttempt,
    Plan,
    Subscription,
    UsageCounter,
)
from app.modules.leads.models import Lead
from app.modules.provider_serpapi.models import ProviderFetch
from app.modules.search_jobs.models import SearchJob
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


def _seed_platform_fixture(db: Session) -> dict[str, str]:
    db.add_all(
        [
            Role(key="platform_admin", label="Platform Admin"),
            Role(key="account_owner", label="Account Owner"),
            Role(key="admin", label="Administrator"),
            Role(key="manager", label="Manager"),
            Role(key="member", label="Member"),
        ]
    )
    ops_workspace = Workspace(name="Ops", slug="ops", status="active")
    customer_workspace = Workspace(name="Acme", slug="acme", status="active")
    db.add_all([ops_workspace, customer_workspace])
    db.flush()

    platform_admin = User(
        workspace_id=ops_workspace.id,
        email="platform@example.com",
        full_name="Platform Admin",
        hashed_password=hash_password("PlatformPass123!"),
        role="platform_admin",
        status="active",
    )
    owner = User(
        workspace_id=customer_workspace.id,
        email="owner@example.com",
        full_name="Workspace Owner",
        hashed_password=hash_password("OwnerPass123!"),
        role="account_owner",
        status="active",
    )
    member = User(
        workspace_id=customer_workspace.id,
        email="member@example.com",
        full_name="Workspace Member",
        hashed_password=hash_password("MemberPass123!"),
        role="member",
        status="active",
    )
    db.add_all([platform_admin, owner, member])
    db.flush()
    ops_workspace.owner_user_id = platform_admin.id
    customer_workspace.owner_user_id = owner.id

    plan = Plan(code="growth", name="Growth", monthly_price=99, yearly_price=948)
    db.add(plan)
    db.flush()
    subscription = Subscription(
        workspace_id=customer_workspace.id,
        plan_id=plan.id,
        status="active",
        billing_cycle="monthly",
    )
    db.add(subscription)
    db.flush()
    invoice = Invoice(
        workspace_id=customer_workspace.id,
        subscription_id=subscription.id,
        amount=99,
        currency="USD",
        status="open",
    )
    db.add(invoice)
    db.flush()
    db.add(InvoiceItem(invoice_id=invoice.id, description="Growth plan", amount=99, quantity=1))
    db.add(
        PaymentAttempt(
            invoice_id=invoice.id,
            status="failed",
            simulated_result="failure",
            error_message="Simulated card decline.",
        )
    )
    db.add(
        UsageCounter(
            workspace_id=customer_workspace.id,
            metric_key="searches",
            current_value=7,
        )
    )
    job = SearchJob(
        workspace_id=customer_workspace.id,
        requested_by_user_id=owner.id,
        business_type="dentist",
        city="Austin",
        status="failed",
        provider_error_count=1,
    )
    db.add(job)
    db.flush()
    lead = Lead(
        workspace_id=customer_workspace.id,
        search_job_id=job.id,
        company_name="Acme Dental",
        city="Austin",
        review_count=10,
        data_completeness=0.8,
        data_confidence=0.9,
        has_website=True,
    )
    db.add(lead)
    db.flush()
    prompt_template = PromptTemplate(
        workspace_id=customer_workspace.id,
        name="Default",
        template_text="Analyze this lead.",
        created_by_user_id=owner.id,
    )
    db.add(prompt_template)
    db.flush()
    snapshot = AIAnalysisSnapshot(
        lead_id=lead.id,
        prompt_template_id=prompt_template.id,
        ai_provider="test",
        model_name="test-model",
        input_hash="input-hash",
        output_json={
            "confidence": 0.4,
            "risks_or_uncertainties": ["Website ownership is unclear."],
        },
        created_by_user_id=owner.id,
    )
    db.add(snapshot)
    db.flush()
    db.add(
        AIFeedback(
            workspace_id=customer_workspace.id,
            ai_analysis_snapshot_id=snapshot.id,
            user_id=owner.id,
            rating="useful",
            correction_text="Keep this evidence.",
        )
    )
    db.add(
        ProviderFetch(
            workspace_id=customer_workspace.id,
            provider="serpapi",
            engine="google_maps",
            mode="maps_search",
            search_job_id=job.id,
            request_fingerprint="abc123",
            request_params_json={"api_key": "should-not-leak"},
            status="error",
            http_status=429,
            error_message="quota exceeded",
        )
    )
    db.commit()
    return {
        "platform_email": platform_admin.email,
        "owner_email": owner.email,
        "member_email": member.email,
        "member_public_id": member.public_id,
        "workspace_public_id": customer_workspace.public_id,
    }


def _login(client: TestClient, *, email: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_platform_admin_can_read_overview_and_workspace_users_cannot() -> None:
    session_factory = _build_session_factory()
    with session_factory() as db:
        seeded = _seed_platform_fixture(db)

    with _override_client(session_factory) as client:
        platform_token = _login(
            client,
            email=seeded["platform_email"],
            password="PlatformPass123!",
        )
        owner_token = _login(client, email=seeded["owner_email"], password="OwnerPass123!")
        member_token = _login(client, email=seeded["member_email"], password="MemberPass123!")

        platform_response = client.get(
            "/api/v1/admin/overview",
            headers={"Authorization": f"Bearer {platform_token}"},
        )
        owner_response = client.get(
            "/api/v1/admin/overview",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        member_response = client.get(
            "/api/v1/admin/overview",
            headers={"Authorization": f"Bearer {member_token}"},
        )

    assert platform_response.status_code == 200
    assert platform_response.json()["total_workspaces"] == 2
    assert platform_response.json()["total_leads"] == 1
    assert platform_response.json()["failed_search_jobs"] == 1
    assert owner_response.status_code == 403
    assert member_response.status_code == 403


def test_platform_admin_disable_workspace_records_audit_log() -> None:
    session_factory = _build_session_factory()
    with session_factory() as db:
        seeded = _seed_platform_fixture(db)

    with _override_client(session_factory) as client:
        platform_token = _login(
            client,
            email=seeded["platform_email"],
            password="PlatformPass123!",
        )
        response = client.post(
            f"/api/v1/admin/workspaces/{seeded['workspace_public_id']}/disable",
            headers={"Authorization": f"Bearer {platform_token}"},
        )
        blocked_login = client.post(
            "/api/v1/auth/login",
            json={"email": seeded["owner_email"], "password": "OwnerPass123!"},
        )
        enabled = client.post(
            f"/api/v1/admin/workspaces/{seeded['workspace_public_id']}/enable",
            headers={"Authorization": f"Bearer {platform_token}"},
        )
        restored_login = client.post(
            "/api/v1/auth/login",
            json={"email": seeded["owner_email"], "password": "OwnerPass123!"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "disabled"
    assert blocked_login.status_code == 401
    assert blocked_login.json()["error"]["code"] == "workspace.inactive"
    assert enabled.status_code == 200
    assert enabled.json()["status"] == "active"
    assert restored_login.status_code == 200
    with session_factory() as db:
        workspace = db.scalar(
            select(Workspace).where(Workspace.public_id == seeded["workspace_public_id"])
        )
        assert workspace is not None
        assert workspace.status == "active"
        audit_events = set(
            db.scalars(
                select(AuditLog.event_name).where(
                    AuditLog.event_name.like("platform_admin.workspace_%")
                )
            )
        )
        assert "platform_admin.workspace_disabled" in audit_events
        assert "platform_admin.workspace_enabled" in audit_events


def test_platform_admin_can_disable_and_enable_user() -> None:
    session_factory = _build_session_factory()
    with session_factory() as db:
        seeded = _seed_platform_fixture(db)

    with _override_client(session_factory) as client:
        platform_token = _login(
            client,
            email=seeded["platform_email"],
            password="PlatformPass123!",
        )
        disabled = client.post(
            f"/api/v1/admin/users/{seeded['member_public_id']}/disable",
            headers={"Authorization": f"Bearer {platform_token}"},
        )
        enabled = client.post(
            f"/api/v1/admin/users/{seeded['member_public_id']}/enable",
            headers={"Authorization": f"Bearer {platform_token}"},
        )

    assert disabled.status_code == 200
    assert disabled.json()["status"] == "inactive"
    assert enabled.status_code == 200
    assert enabled.json()["status"] == "active"
    with session_factory() as db:
        user = db.scalar(select(User).where(User.public_id == seeded["member_public_id"]))
        assert user is not None
        assert user.status == "active"
        audit_events = set(
            db.scalars(
                select(AuditLog.event_name).where(AuditLog.event_name.like("platform_admin.user_%"))
            )
        )
        assert "platform_admin.user_disabled" in audit_events
        assert "platform_admin.user_enabled" in audit_events


def test_platform_admin_workspace_detail_and_billing_include_real_operational_rows() -> None:
    session_factory = _build_session_factory()
    with session_factory() as db:
        seeded = _seed_platform_fixture(db)

    with _override_client(session_factory) as client:
        platform_token = _login(
            client,
            email=seeded["platform_email"],
            password="PlatformPass123!",
        )
        workspace_response = client.get(
            f"/api/v1/admin/workspaces/{seeded['workspace_public_id']}",
            headers={"Authorization": f"Bearer {platform_token}"},
        )
        invoices_response = client.get(
            "/api/v1/admin/invoices",
            headers={"Authorization": f"Bearer {platform_token}"},
        )

    assert workspace_response.status_code == 200
    workspace_body = workspace_response.json()
    assert len(workspace_body["users"]) == 2
    assert workspace_body["lead_scores_count"] == 0
    assert workspace_body["ai_evidence_count"] == 0
    assert len(workspace_body["recent_provider_errors"]) == 1

    assert invoices_response.status_code == 200
    invoice = invoices_response.json()["items"][0]
    assert invoice["status"] == "open"
    assert invoice["items"][0]["description"] == "Growth plan"
    assert invoice["payment_attempts"][0]["simulated_result"] == "failure"


def test_platform_provider_admin_does_not_expose_request_params_or_secrets() -> None:
    session_factory = _build_session_factory()
    with session_factory() as db:
        seeded = _seed_platform_fixture(db)

    with _override_client(session_factory) as client:
        platform_token = _login(
            client,
            email=seeded["platform_email"],
            password="PlatformPass123!",
        )
        response = client.get(
            "/api/v1/admin/providers",
            headers={"Authorization": f"Bearer {platform_token}"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["failure_count"] == 1
    assert len(body["recent_errors"]) == 1
    assert "request_params_json" not in str(body)
    assert "should-not-leak" not in str(body)


def test_platform_ai_usage_surfaces_feedback_and_flagged_analyses() -> None:
    session_factory = _build_session_factory()
    with session_factory() as db:
        seeded = _seed_platform_fixture(db)

    with _override_client(session_factory) as client:
        platform_token = _login(
            client,
            email=seeded["platform_email"],
            password="PlatformPass123!",
        )
        response = client.get(
            "/api/v1/admin/ai-usage",
            headers={"Authorization": f"Bearer {platform_token}"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["analyses_count"] == 1
    assert body["feedback_counts"] == [{"rating": "useful", "count": 1}]
    assert body["latest_feedback"][0]["correction_text"] == "Keep this evidence."
    assert body["flagged_analyses"][0]["lead_name"] == "Acme Dental"
    assert body["flagged_analyses"][0]["confidence"] == 0.4
    assert body["flagged_analyses"][0]["risks_or_uncertainties"] == [
        "Website ownership is unclear."
    ]
