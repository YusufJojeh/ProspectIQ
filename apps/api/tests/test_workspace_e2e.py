from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.modules.ai_analysis.models import PromptTemplate
from app.modules.leads.models import Lead
from app.modules.provider_serpapi.models import (
    ProviderFetch,
    ProviderNormalizedFact,
    ProviderRawPayload,
    ProviderSettings,
)
from app.modules.scoring.models import (
    LeadScore,
    ScoreBreakdown,
    ScoringConfigVersion,
    WorkspaceScoringActive,
)
from app.modules.scoring.schemas import ScoringThresholds, ScoringWeights
from app.modules.search_jobs.models import SearchJob, SearchRequest
from app.modules.users.models import Role, User, Workspace


@dataclass(frozen=True)
class _SeededWorkspace:
    workspace_public_id: str
    admin_email: str
    admin_password: str
    manager_public_id: str
    lead_public_id: str


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


def _seed_workspace(session_factory: sessionmaker[Session]) -> _SeededWorkspace:
    admin_password = "AdminPass123"
    with session_factory() as db:
        db.add_all(
            [
                Role(key="admin", label="Administrator"),
                Role(key="agency_manager", label="Agency Manager"),
                Role(key="sales_user", label="Sales User"),
            ]
        )
        db.commit()

        workspace = Workspace(public_id="ws_test", name="LeadScope Test Workspace")
        db.add(workspace)
        db.commit()
        db.refresh(workspace)

        admin = User(
            workspace_id=workspace.id,
            email="admin@example.com",
            full_name="Admin User",
            hashed_password=hash_password(admin_password),
            role="admin",
        )
        manager = User(
            workspace_id=workspace.id,
            email="manager@example.com",
            full_name="Manager User",
            hashed_password=hash_password("ManagerPass123"),
            role="agency_manager",
        )
        sales = User(
            workspace_id=workspace.id,
            email="sales@example.com",
            full_name="Sales User",
            hashed_password=hash_password("SalesPass123"),
            role="sales_user",
        )
        db.add_all([admin, manager, sales])
        db.commit()
        db.refresh(admin)
        db.refresh(manager)

        provider_settings = ProviderSettings(
            workspace_id=workspace.id,
            hl="en",
            gl="tr",
            google_domain="google.com",
            enrich_top_n=10,
        )
        db.add(provider_settings)

        prompt_template = PromptTemplate(
            workspace_id=workspace.id,
            name="Default lead analysis",
            template_text="Use stored facts only.",
            is_active=True,
            created_by_user_id=admin.id,
        )
        db.add(prompt_template)

        scoring_version = ScoringConfigVersion(
            workspace_id=workspace.id,
            created_by_user_id=admin.id,
            weights_json=ScoringWeights().model_dump(),
            thresholds_json=ScoringThresholds().model_dump(),
            note="Seeded scoring policy",
        )
        db.add(scoring_version)
        db.commit()
        db.refresh(scoring_version)

        db.add(
            WorkspaceScoringActive(
                workspace_id=workspace.id,
                active_scoring_config_version_id=scoring_version.id,
            )
        )
        db.commit()

        search_request = SearchRequest(
            workspace_id=workspace.id,
            requested_by_user_id=admin.id,
            business_type="Dentist",
            city="Istanbul",
            region="Kadikoy",
            radius_km=10,
            max_results=25,
            min_rating=4.0,
            max_rating=5.0,
            min_reviews=10,
            max_reviews=200,
            website_preference="must_have",
            keyword_filter="implant",
        )
        db.add(search_request)
        db.commit()
        db.refresh(search_request)

        search_job = SearchJob(
            workspace_id=workspace.id,
            search_request_id=search_request.id,
            requested_by_user_id=admin.id,
            business_type="Dentist",
            city="Istanbul",
            region="Kadikoy",
            radius_km=10,
            max_results=25,
            min_rating=4.0,
            max_rating=5.0,
            min_reviews=10,
            max_reviews=200,
            website_preference="must_have",
            keyword_filter="implant",
            status="completed",
            candidates_found=3,
            leads_upserted=1,
            enriched_count=1,
            provider_error_count=0,
        )
        db.add(search_job)
        db.commit()
        db.refresh(search_job)

        lead = Lead(
            workspace_id=workspace.id,
            search_job_id=search_job.id,
            company_name="Acme Dental",
            category="Dentist",
            address="Bagdat Avenue, Istanbul, Turkey",
            city="Istanbul",
            phone="+90 555 111 2233",
            website_url="https://acmedental.example",
            website_domain="acmedental.example",
            review_count=24,
            rating=4.7,
            lat=41.015,
            lng=29.042,
            data_completeness=0.84,
            data_confidence=0.88,
            has_website=True,
            status="reviewed",
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)

        fetch = ProviderFetch(
            workspace_id=workspace.id,
            provider="serpapi",
            engine="google_maps",
            mode="maps_place",
            search_job_id=search_job.id,
            request_fingerprint="seed-fetch",
            request_params_json={"mode": "maps_place"},
            serpapi_search_id="seed-search-id",
            status="ok",
            http_status=200,
            started_at=datetime.now(tz=UTC),
            finished_at=datetime.now(tz=UTC),
            attempt=1,
        )
        db.add(fetch)
        db.commit()
        db.refresh(fetch)

        db.add(
            ProviderRawPayload(
                provider_fetch_id=fetch.id,
                payload_json={"place_results": {"title": lead.company_name}},
                payload_sha256="seed-payload-sha",
            )
        )
        db.add(
            ProviderNormalizedFact(
                workspace_id=workspace.id,
                lead_id=lead.id,
                provider_fetch_id=fetch.id,
                source_type="maps_place",
                data_cid="123456789",
                data_id="0xabc:0xdef",
                place_id="ChIJAcmeDental",
                company_name=lead.company_name,
                category=lead.category,
                address=lead.address,
                city=lead.city,
                phone=lead.phone,
                website_url=lead.website_url,
                website_domain=lead.website_domain,
                rating=lead.rating,
                review_count=lead.review_count,
                lat=lead.lat,
                lng=lead.lng,
                confidence=0.88,
                completeness=0.84,
                facts_json={"website": lead.website_url, "source": "maps_place"},
            )
        )
        db.commit()

        lead_score = LeadScore(
            lead_id=lead.id,
            scoring_config_version_id=scoring_version.id,
            total_score=82.5,
            band="high",
            qualified=True,
        )
        db.add(lead_score)
        db.commit()
        db.refresh(lead_score)

        db.add_all(
            [
                ScoreBreakdown(
                    lead_score_id=lead_score.id,
                    key="website_presence",
                    label="Website presence",
                    weight=0.25,
                    contribution=21.0,
                    reason="An official website is present and discoverable.",
                ),
                ScoreBreakdown(
                    lead_score_id=lead_score.id,
                    key="local_trust",
                    label="Local trust",
                    weight=0.25,
                    contribution=24.0,
                    reason="High rating with strong review volume.",
                ),
            ]
        )
        db.commit()

        return _SeededWorkspace(
            workspace_public_id=workspace.public_id,
            admin_email=admin.email,
            admin_password=admin_password,
            manager_public_id=manager.public_id,
            lead_public_id=lead.public_id,
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


def _login(client: TestClient, seed: _SeededWorkspace) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "workspace": seed.workspace_public_id,
            "email": seed.admin_email,
            "password": seed.admin_password,
        },
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_workspace_operator_journey_e2e(monkeypatch) -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    monkeypatch.setattr(
        "app.modules.search_jobs.api.LeadDiscoveryOrchestrator.run",
        lambda self, job_public_id: None,
    )

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        headers = {"Authorization": f"Bearer {token}"}

        me_response = client.get("/api/v1/me", headers=headers)
        users_response = client.get("/api/v1/users", headers=headers)
        provider_response = client.get("/api/v1/admin/provider-settings", headers=headers)
        active_scoring_response = client.get("/api/v1/admin/scoring-config/active", headers=headers)

        assert me_response.status_code == 200
        assert me_response.json()["role"] == "admin"
        assert users_response.status_code == 200
        assert len(users_response.json()["items"]) == 3
        assert provider_response.status_code == 200
        assert provider_response.json()["enrich_top_n"] == 10
        assert active_scoring_response.status_code == 200

        update_provider_response = client.patch(
            "/api/v1/admin/provider-settings",
            headers=headers,
            json={"gl": "us", "enrich_top_n": 15},
        )
        assert update_provider_response.status_code == 200
        assert update_provider_response.json()["gl"] == "us"
        assert update_provider_response.json()["enrich_top_n"] == 15

        create_scoring_response = client.post(
            "/api/v1/admin/scoring-config/versions",
            headers=headers,
            json={
                "weights": {
                    "local_trust": 0.3,
                    "website_presence": 0.2,
                    "search_visibility": 0.2,
                    "opportunity": 0.2,
                    "data_confidence": 0.1,
                },
                "thresholds": {
                    "high_min": 78,
                    "medium_min": 58,
                    "low_min": 38,
                    "confidence_min": 0.5,
                },
                "note": "E2E scoring version",
            },
        )
        assert create_scoring_response.status_code == 200
        version_public_id = create_scoring_response.json()["public_id"]

        activate_response = client.post(
            f"/api/v1/admin/scoring-config/activate/{version_public_id}",
            headers=headers,
        )
        assert activate_response.status_code == 200
        assert activate_response.json()["active_version"]["public_id"] == version_public_id

        create_job_response = client.post(
            "/api/v1/search-jobs",
            headers=headers,
            json={
                "business_type": "Lawyer",
                "city": "Ankara",
                "radius_km": 12,
                "max_results": 20,
                "min_rating": 4.2,
                "website_preference": "must_be_missing",
                "keyword_filter": "family",
            },
        )
        assert create_job_response.status_code == 202
        created_job = create_job_response.json()
        assert created_job["status"] == "queued"

        list_jobs_response = client.get("/api/v1/search-jobs", headers=headers)
        assert list_jobs_response.status_code == 200
        assert len(list_jobs_response.json()["items"]) == 2

        list_leads_response = client.get("/api/v1/leads?page_size=50", headers=headers)
        assert list_leads_response.status_code == 200
        assert list_leads_response.json()["items"][0]["public_id"] == seed.lead_public_id

        get_lead_response = client.get(f"/api/v1/leads/{seed.lead_public_id}", headers=headers)
        assert get_lead_response.status_code == 200
        assert get_lead_response.json()["latest_band"] == "high"

        assign_response = client.patch(
            f"/api/v1/leads/{seed.lead_public_id}/assign",
            headers=headers,
            json={"assignee_user_public_id": seed.manager_public_id},
        )
        assert assign_response.status_code == 200
        assert assign_response.json()["assigned_to_user_public_id"] == seed.manager_public_id

        update_status_response = client.patch(
            f"/api/v1/leads/{seed.lead_public_id}/status",
            headers=headers,
            json={"status": "qualified", "note": "Qualified after evidence review."},
        )
        assert update_status_response.status_code == 200
        assert update_status_response.json()["status"] == "qualified"

        note_response = client.post(
            f"/api/v1/leads/{seed.lead_public_id}/notes",
            headers=headers,
            json={"note": "Call this lead during the afternoon shift."},
        )
        assert note_response.status_code == 200
        assert "afternoon shift" in note_response.json()["note"]

        activity_response = client.get(
            f"/api/v1/leads/{seed.lead_public_id}/activity",
            headers=headers,
        )
        assert activity_response.status_code == 200
        activity_items = activity_response.json()["items"]
        assert len(activity_items) >= 3
        assert {item["entry_type"] for item in activity_items} == {"status_change", "note"}

        evidence_response = client.get(
            f"/api/v1/leads/{seed.lead_public_id}/evidence",
            headers=headers,
        )
        assert evidence_response.status_code == 200
        assert evidence_response.json()["items"][0]["provider_status"] == "ok"

        breakdown_response = client.get(
            f"/api/v1/leads/{seed.lead_public_id}/score-breakdown",
            headers=headers,
        )
        assert breakdown_response.status_code == 200
        assert breakdown_response.json()["total_score"] == 82.5

        analyze_response = client.post(
            f"/api/v1/leads/{seed.lead_public_id}/analyze",
            headers=headers,
        )
        assert analyze_response.status_code == 200
        assert "Acme Dental" in analyze_response.json()["analysis"]["summary"]

        latest_analysis_response = client.get(
            f"/api/v1/ai-analysis/leads/{seed.lead_public_id}/latest",
            headers=headers,
        )
        assert latest_analysis_response.status_code == 200
        assert latest_analysis_response.json()["snapshot"] is not None

        outreach_response = client.post(
            f"/api/v1/leads/{seed.lead_public_id}/outreach/generate",
            headers=headers,
        )
        assert outreach_response.status_code == 200
        assert outreach_response.json()["lead_id"] == seed.lead_public_id

        latest_outreach_response = client.get(
            f"/api/v1/outreach/leads/{seed.lead_public_id}/latest",
            headers=headers,
        )
        assert latest_outreach_response.status_code == 200
        latest_outreach = latest_outreach_response.json()["message"]
        assert latest_outreach is not None

        update_outreach_response = client.patch(
            f"/api/v1/outreach/messages/{latest_outreach['public_id']}",
            headers=headers,
            json={
                "subject": "Quick visibility idea for Acme Dental",
                "message": "We found two local search improvements worth discussing this week.",
            },
        )
        assert update_outreach_response.status_code == 200
        assert update_outreach_response.json()["has_manual_edits"] is True

        csv_response = client.get("/api/v1/exports/leads.csv", headers=headers)
        assert csv_response.status_code == 200
        assert "Acme Dental" in csv_response.text
        assert "text/csv" in csv_response.headers["content-type"]

        audit_response = client.get("/api/v1/audit-logs", headers=headers)
        assert audit_response.status_code == 200
        audit_events = {item["event_name"] for item in audit_response.json()["items"]}
        assert {
            "auth.login",
            "lead.status_updated",
            "lead.note_added",
            "lead.outreach_generated",
            "leads.exported_csv",
        }.issubset(audit_events)
