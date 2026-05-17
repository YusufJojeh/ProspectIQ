from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.workers.orchestration.lead_discovery as lead_discovery_module
from app.core.config import clear_settings_cache
from app.core.database import Base
from app.modules.leads.models import Lead
from app.modules.provider_serpapi.models import (
    LeadIdentity,
    ProviderFetch,
    ProviderNormalizedFact,
    ProviderRawPayload,
)
from app.modules.provider_serpapi.schemas import PlaceLookupKey
from app.modules.scoring.models import LeadScore
from app.modules.search_jobs.models import SearchJob
from app.modules.users.models import User, Workspace
from app.shared.enums.jobs import ProviderFetchStatus, SearchJobStatus, WebsitePreference
from app.workers.orchestration.lead_discovery import (
    ORCHESTRATION_TIMEOUT_SECONDS,
    LeadDiscoveryOrchestrator,
)


@dataclass
class _ProviderSettings:
    enrich_top_n: int = 0
    hl: str = "en"
    gl: str = "us"
    google_domain: str = "google.com"


class _FakeProviderService:
    def __init__(
        self,
        *,
        search_payload: dict,
        web_payload: dict | None = None,
        web_status: str = ProviderFetchStatus.OK.value,
        enrich_top_n: int = 0,
    ) -> None:
        self.search_payload = search_payload
        self.web_payload = web_payload or {}
        self.web_status = web_status
        self._enrich_top_n = enrich_top_n

    def get_settings(self, db: Session, workspace_id: int) -> _ProviderSettings:  # noqa: ARG002
        return _ProviderSettings(enrich_top_n=self._enrich_top_n)

    def maps_search(
        self,
        db: Session,
        *,
        workspace_id: int,
        search_job_id: int,
        business_type: str,  # noqa: ARG002
        city: str,  # noqa: ARG002
        region: str | None,  # noqa: ARG002
        radius_km: int | None = None,  # noqa: ARG002
        keyword_filter: str | None = None,  # noqa: ARG002
        page: int = 1,  # noqa: ARG002
        attempt: int = 1,
    ):
        return self._persist_fetch(
            db,
            workspace_id=workspace_id,
            search_job_id=search_job_id,
            mode="maps_search",
            payload=self.search_payload,
            status=ProviderFetchStatus.OK.value,
            attempt=attempt,
        )

    def maps_place(
        self,
        db: Session,
        *,
        workspace_id: int,
        search_job_id: int | None,
        lookup: PlaceLookupKey,  # noqa: ARG002
        attempt: int = 1,
    ):
        return self._persist_fetch(
            db,
            workspace_id=workspace_id,
            search_job_id=search_job_id,
            mode="maps_place",
            payload={},
            status=ProviderFetchStatus.ERROR.value,
            attempt=attempt,
        )

    def web_search(
        self,
        db: Session,
        *,
        workspace_id: int,
        search_job_id: int | None,
        query: str,  # noqa: ARG002
        attempt: int = 1,
    ):
        return self._persist_fetch(
            db,
            workspace_id=workspace_id,
            search_job_id=search_job_id,
            mode="web_search",
            payload=self.web_payload,
            status=self.web_status,
            attempt=attempt,
        )

    def _persist_fetch(
        self,
        db: Session,
        *,
        workspace_id: int,
        search_job_id: int | None,
        mode: str,
        payload: dict,
        status: str,
        attempt: int,
    ):
        fetch = ProviderFetch(
            workspace_id=workspace_id,
            provider="serpapi",
            engine="google_maps" if mode != "web_search" else "google",
            mode=mode,
            search_job_id=search_job_id,
            request_fingerprint=f"{mode}-{attempt}",
            request_params_json={"mode": mode},
            serpapi_search_id=f"{mode}-search-id",
            status=status,
            http_status=200 if status == ProviderFetchStatus.OK.value else 429,
            started_at=datetime.now(tz=UTC),
            finished_at=datetime.now(tz=UTC),
            error_message=None if status == ProviderFetchStatus.OK.value else "provider failed",
            attempt=attempt,
        )
        db.add(fetch)
        db.commit()
        db.refresh(fetch)
        db.add(
            ProviderRawPayload(
                provider_fetch_id=fetch.id,
                payload_json=payload,
                payload_sha256=f"sha-{mode}-{attempt}",
            )
        )
        db.commit()
        return fetch, payload


def _build_session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session
    )


def _seed_job(session_factory: sessionmaker[Session]) -> str:
    with session_factory() as db:
        workspace = Workspace(name="Test Workspace")
        db.add(workspace)
        db.commit()
        db.refresh(workspace)

        user = User(
            workspace_id=workspace.id,
            email="admin@example.com",
            full_name="Admin User",
            hashed_password="hashed",
            role="admin",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        job = SearchJob(
            workspace_id=workspace.id,
            requested_by_user_id=user.id,
            business_type="Dentist",
            city="Istanbul",
            max_results=10,
            website_preference=WebsitePreference.ANY.value,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job.public_id


def test_orchestrator_persists_leads_evidence_and_scores() -> None:
    session_factory = _build_session_factory()
    job_public_id = _seed_job(session_factory)
    provider = _FakeProviderService(
        search_payload={
            "local_results": [
                {
                    "title": "Acme Dental",
                    "address": "Bagdat Avenue, Istanbul, Turkey",
                    "phone": "+90 555 111 2233",
                    "rating": 4.5,
                    "reviews": 12,
                    "gps_coordinates": {"latitude": 41.01, "longitude": 29.05},
                    "data_id": "maps-acme-1",
                    "type": "Dentist",
                }
            ]
        },
        web_payload={"knowledge_graph": {"website": "https://acme.example"}},
    )

    LeadDiscoveryOrchestrator(session_factory=session_factory, provider_service=provider).run(
        job_public_id
    )

    with session_factory() as db:
        job = db.scalar(select(SearchJob).where(SearchJob.public_id == job_public_id))
        assert job is not None
        assert job.status == SearchJobStatus.COMPLETED.value
        assert job.candidates_found == 1
        assert job.leads_upserted == 1
        assert job.provider_error_count == 0

        lead = db.scalar(select(Lead).where(Lead.search_job_id == job.id))
        assert lead is not None
        assert lead.company_name == "Acme Dental"
        assert lead.website_domain == "acme.example"
        assert lead.has_website is True

        assert db.scalar(select(func.count(LeadIdentity.id))) == 3
        assert db.scalar(select(func.count(ProviderNormalizedFact.id))) == 2
        assert db.scalar(select(func.count(LeadScore.id))) == 1


def test_orchestrator_marks_job_partially_completed_on_secondary_provider_failure() -> None:
    session_factory = _build_session_factory()
    job_public_id = _seed_job(session_factory)
    provider = _FakeProviderService(
        search_payload={
            "local_results": [
                {
                    "title": "North Clinic",
                    "address": "Kadikoy, Istanbul, Turkey",
                    "phone": "+90 555 999 8899",
                    "rating": 4.2,
                    "reviews": 5,
                    "gps_coordinates": {"latitude": 41.02, "longitude": 29.01},
                    "data_id": "maps-north-1",
                    "type": "Clinic",
                }
            ]
        },
        web_payload={},
        web_status=ProviderFetchStatus.ERROR.value,
    )

    LeadDiscoveryOrchestrator(session_factory=session_factory, provider_service=provider).run(
        job_public_id
    )

    with session_factory() as db:
        job = db.scalar(select(SearchJob).where(SearchJob.public_id == job_public_id))
        assert job is not None
        assert job.status == SearchJobStatus.PARTIALLY_COMPLETED.value
        assert job.leads_upserted == 1
        assert job.provider_error_count == 1
        assert db.scalar(select(func.count(ProviderNormalizedFact.id))) == 1
        assert db.scalar(select(func.count(LeadScore.id))) == 1


def test_orchestrator_marks_job_failed_when_live_provider_is_unconfigured(monkeypatch) -> None:
    monkeypatch.setenv("SERPAPI_API_KEY", "")
    monkeypatch.setenv("SERPAPI_RUNTIME_MODE", "blocked")
    clear_settings_cache()
    session_factory = _build_session_factory()
    job_public_id = _seed_job(session_factory)

    LeadDiscoveryOrchestrator(session_factory=session_factory).run(job_public_id)

    with session_factory() as db:
        job = db.scalar(select(SearchJob).where(SearchJob.public_id == job_public_id))
        assert job is not None
        assert job.status == SearchJobStatus.FAILED.value
        assert job.leads_upserted == 0
        assert db.scalar(select(func.count(ProviderFetch.id))) == 0
        assert db.scalar(select(func.count(LeadScore.id))) == 0

    clear_settings_cache()


def test_orchestrator_marks_job_failed_when_discovery_is_blocked(monkeypatch) -> None:
    """Deterministic: does not depend on host .env, SERPAPI_API_KEY, or demo fallbacks."""
    clear_settings_cache()
    session_factory = _build_session_factory()
    job_public_id = _seed_job(session_factory)

    class _BlockedSettings:
        discovery_runtime = "blocked"

    monkeypatch.setattr(
        "app.workers.orchestration.lead_discovery.get_settings",
        lambda: _BlockedSettings(),
    )

    LeadDiscoveryOrchestrator(session_factory=session_factory).run(job_public_id)

    with session_factory() as db:
        job = db.scalar(select(SearchJob).where(SearchJob.public_id == job_public_id))
        assert job is not None
        assert job.status == SearchJobStatus.FAILED.value
        assert job.provider_error_count == 1
        assert job.finished_at is not None

    clear_settings_cache()


def test_run_skips_enrichment_when_orchestration_deadline_is_immediate(monkeypatch) -> None:
    """Integration-style: zero-second budget makes enrich exit before maps_place (full run())."""
    monkeypatch.setattr(lead_discovery_module, "ORCHESTRATION_TIMEOUT_SECONDS", 0)
    clear_settings_cache()
    session_factory = _build_session_factory()
    job_public_id = _seed_job(session_factory)

    provider = _FakeProviderService(
        search_payload={
            "local_results": [
                {
                    "title": "Acme Dental",
                    "address": "Bagdat Avenue, Istanbul, Turkey",
                    "phone": "+90 555 111 2233",
                    "rating": 4.5,
                    "reviews": 12,
                    "gps_coordinates": {"latitude": 41.01, "longitude": 29.05},
                    "data_id": "maps-acme-1",
                    "type": "Dentist",
                }
            ]
        },
        web_payload={"knowledge_graph": {"website": "https://acme.example"}},
        enrich_top_n=5,
    )
    maps_calls = {"n": 0}
    orig_maps = provider.maps_place

    def counting_maps(*a, **k):
        maps_calls["n"] += 1
        return orig_maps(*a, **k)

    provider.maps_place = counting_maps

    LeadDiscoveryOrchestrator(session_factory=session_factory, provider_service=provider).run(
        job_public_id
    )

    assert maps_calls["n"] == 0
    with session_factory() as db:
        job = db.scalar(select(SearchJob).where(SearchJob.public_id == job_public_id))
        assert job is not None
        assert job.status == SearchJobStatus.COMPLETED.value
        assert job.leads_upserted == 1

    clear_settings_cache()


def test_enrich_top_candidates_skips_maps_place_when_deadline_elapsed() -> None:
    session_factory = _build_session_factory()
    job_public_id = _seed_job(session_factory)
    discovery_provider = _FakeProviderService(
        search_payload={
            "local_results": [
                {
                    "title": "Acme Dental",
                    "address": "Bagdat Avenue, Istanbul, Turkey",
                    "phone": "+90 555 111 2233",
                    "rating": 4.5,
                    "reviews": 12,
                    "gps_coordinates": {"latitude": 41.01, "longitude": 29.05},
                    "data_id": "maps-acme-1",
                    "type": "Dentist",
                }
            ]
        },
        web_payload={"knowledge_graph": {"website": "https://acme.example"}},
        enrich_top_n=0,
    )
    LeadDiscoveryOrchestrator(
        session_factory=session_factory, provider_service=discovery_provider
    ).run(job_public_id)

    enrich_provider = _FakeProviderService(
        search_payload={"local_results": []},
        enrich_top_n=5,
    )
    maps_calls = {"n": 0}
    orig_maps = enrich_provider.maps_place

    def counting_maps(*a, **k):
        maps_calls["n"] += 1
        return orig_maps(*a, **k)

    enrich_provider.maps_place = counting_maps

    orch = LeadDiscoveryOrchestrator(
        session_factory=session_factory, provider_service=enrich_provider
    )
    deadline = datetime.now(tz=UTC) - timedelta(seconds=1)
    with session_factory() as db:
        job = db.scalar(select(SearchJob).where(SearchJob.public_id == job_public_id))
        assert job is not None
        lead = db.scalar(select(Lead).where(Lead.search_job_id == job.id))
        assert lead is not None
        orch._enrich_top_candidates(db, job, [lead.id], deadline=deadline)

    assert maps_calls["n"] == 0


def test_validate_web_presence_skips_web_search_when_deadline_elapsed() -> None:
    session_factory = _build_session_factory()
    job_public_id = _seed_job(session_factory)
    provider = _FakeProviderService(
        search_payload={
            "local_results": [
                {
                    "title": "Acme Dental",
                    "address": "Bagdat Avenue, Istanbul, Turkey",
                    "phone": "+90 555 111 2233",
                    "rating": 4.5,
                    "reviews": 12,
                    "gps_coordinates": {"latitude": 41.01, "longitude": 29.05},
                    "data_id": "maps-acme-1",
                    "type": "Dentist",
                }
            ]
        },
        web_payload={},
        web_status=ProviderFetchStatus.OK.value,
    )
    LeadDiscoveryOrchestrator(session_factory=session_factory, provider_service=provider).run(
        job_public_id
    )

    web_calls = {"n": 0}
    orig_web = provider.web_search

    def counting_web(*a, **k):
        web_calls["n"] += 1
        return orig_web(*a, **k)

    provider.web_search = counting_web

    orch = LeadDiscoveryOrchestrator(session_factory=session_factory, provider_service=provider)
    deadline = datetime.now(tz=UTC) - timedelta(seconds=1)
    with session_factory() as db:
        job = db.scalar(select(SearchJob).where(SearchJob.public_id == job_public_id))
        assert job is not None
        lead = db.scalar(select(Lead).where(Lead.search_job_id == job.id))
        assert lead is not None
        lead.website_domain = None
        lead.has_website = False
        db.add(lead)
        db.commit()
        orch._validate_web_presence(db, job, [lead.id], deadline=deadline)

    assert web_calls["n"] == 0


def test_orchestration_timeout_constant_is_five_minutes() -> None:
    assert ORCHESTRATION_TIMEOUT_SECONDS == 300


def test_pipeline_mode_runs_arabic_and_english_without_breaking(monkeypatch) -> None:
    monkeypatch.setenv("DISCOVERY_KILL_SWITCH", "false")
    monkeypatch.setenv("DISCOVERY_MODE", "multi_engine_multi_query")
    monkeypatch.setenv("DISCOVERY_MAX_CALLS_PER_JOB", "4")
    clear_settings_cache()
    session_factory = _build_session_factory()
    job_public_id = _seed_job(session_factory)
    provider = _FakeProviderService(
        search_payload={
            "local_results": [
                {
                    "title": "التطوير العقاري",
                    "address": "Riyadh",
                    "phone": "+966 11 555 1000",
                    "rating": 4.8,
                    "reviews": 30,
                    "gps_coordinates": {"latitude": 24.71, "longitude": 46.67},
                    "data_id": "maps-ar-1",
                    "type": "Real Estate",
                }
            ]
        },
        web_payload={"knowledge_graph": {"website": "https://arabic-example.test"}},
    )
    LeadDiscoveryOrchestrator(session_factory=session_factory, provider_service=provider).run(
        job_public_id
    )
    with session_factory() as db:
        job = db.scalar(select(SearchJob).where(SearchJob.public_id == job_public_id))
        assert job is not None
        assert job.status in {SearchJobStatus.COMPLETED.value, SearchJobStatus.PARTIALLY_COMPLETED.value}
        assert job.leads_upserted >= 1
    clear_settings_cache()


def test_single_path_mode_keeps_regression_equivalence(monkeypatch) -> None:
    monkeypatch.setenv("DISCOVERY_KILL_SWITCH", "false")
    monkeypatch.setenv("DISCOVERY_MODE", "single_path")
    clear_settings_cache()
    session_factory = _build_session_factory()
    job_public_id = _seed_job(session_factory)
    provider = _FakeProviderService(
        search_payload={
            "local_results": [
                {
                    "title": "Acme Dental",
                    "address": "Bagdat Avenue, Istanbul, Turkey",
                    "phone": "+90 555 111 2233",
                    "rating": 4.5,
                    "reviews": 12,
                    "gps_coordinates": {"latitude": 41.01, "longitude": 29.05},
                    "data_id": "maps-acme-1",
                    "type": "Dentist",
                }
            ]
        },
        web_payload={"knowledge_graph": {"website": "https://acme.example"}},
    )

    LeadDiscoveryOrchestrator(session_factory=session_factory, provider_service=provider).run(
        job_public_id
    )
    with session_factory() as db:
        job = db.scalar(select(SearchJob).where(SearchJob.public_id == job_public_id))
        lead = db.scalar(select(Lead).where(Lead.search_job_id == job.id)) if job else None
        assert job is not None
        assert job.candidates_found == 1
        assert job.leads_upserted == 1
        assert lead is not None
        assert lead.company_name == "Acme Dental"
    clear_settings_cache()
