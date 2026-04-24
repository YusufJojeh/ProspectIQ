from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import clear_settings_cache
from app.core.database import Base
from app.core.errors import ServiceUnavailableError
from app.modules.leads.models import Lead
from app.modules.provider_serpapi.models import ProviderFetch, ProviderNormalizedFact
from app.modules.provider_serpapi.schemas import PlaceLookupKey
from app.modules.scoring.models import LeadScore
from app.modules.search_jobs.models import SearchJob
from app.modules.users.models import User, Workspace
from app.shared.enums.jobs import ProviderFetchStatus, WebsitePreference
from app.workers.orchestration.lead_refresh import LeadRefreshOrchestrator


@dataclass
class _ProviderSettings:
    enrich_top_n: int = 0


class _FakeRefreshProviderService:
    def __init__(
        self,
        *,
        maps_place_payload: dict,
        web_payload: dict | None = None,
        maps_place_status: str = ProviderFetchStatus.OK.value,
        web_status: str = ProviderFetchStatus.OK.value,
    ) -> None:
        self.maps_place_payload = maps_place_payload
        self.web_payload = web_payload or {}
        self.maps_place_status = maps_place_status
        self.web_status = web_status

    def get_settings(self, db: Session, workspace_id: int) -> _ProviderSettings:  # noqa: ARG002
        return _ProviderSettings()

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
            payload=self.maps_place_payload,
            status=self.maps_place_status,
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
            engine="google_maps" if mode == "maps_place" else "google",
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


def _seed_refresh_target(session_factory: sessionmaker[Session]) -> tuple[int, int, int]:
    with session_factory() as db:
        workspace = Workspace(name="LeadScope Workspace")
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

        lead = Lead(
            workspace_id=workspace.id,
            search_job_id=job.id,
            company_name="Acme Dental",
            category="Dentist",
            address="Bagdat Avenue, Istanbul, Turkey",
            city="Istanbul",
            phone="+905551112233",
            review_count=5,
            rating=4.1,
            data_completeness=0.45,
            data_confidence=0.62,
            has_website=False,
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)

        fetch = ProviderFetch(
            workspace_id=workspace.id,
            provider="serpapi",
            engine="google_maps",
            mode="maps_search",
            search_job_id=job.id,
            request_fingerprint="seed-search",
            request_params_json={"mode": "maps_search"},
            serpapi_search_id="seed-search-id",
            status=ProviderFetchStatus.OK.value,
            http_status=200,
            started_at=datetime.now(tz=UTC),
            finished_at=datetime.now(tz=UTC),
            attempt=1,
        )
        db.add(fetch)
        db.commit()
        db.refresh(fetch)

        db.add(
            ProviderNormalizedFact(
                workspace_id=workspace.id,
                lead_id=lead.id,
                provider_fetch_id=fetch.id,
                source_type="maps_search",
                data_cid=None,
                data_id="maps-acme-1",
                place_id="place-acme-1",
                company_name=lead.company_name,
                category=lead.category,
                address=lead.address,
                city=lead.city,
                phone=lead.phone,
                website_url=None,
                website_domain=None,
                rating=lead.rating,
                review_count=lead.review_count,
                lat=41.01,
                lng=29.05,
                confidence=0.62,
                completeness=0.45,
                facts_json={"seed": True},
            )
        )
        db.commit()
        return workspace.id, user.id, lead.id


def test_refresh_orchestrator_enriches_selected_lead_from_maps_place() -> None:
    session_factory = _build_session_factory()
    workspace_id, user_id, lead_id = _seed_refresh_target(session_factory)
    provider = _FakeRefreshProviderService(
        maps_place_payload={
            "place_results": {
                "title": "Acme Dental",
                "address": "Bagdat Avenue, Istanbul, Turkey",
                "phone": "+90 555 111 2233",
                "website": "https://acmedental.example",
                "rating": 4.7,
                "reviews": 18,
                "gps_coordinates": {"latitude": 41.01, "longitude": 29.05},
                "data_id": "maps-acme-1",
                "type": "Dentist",
            }
        }
    )

    with session_factory() as db:
        lead = db.get(Lead, lead_id)
        assert lead is not None
        refreshed = LeadRefreshOrchestrator(provider_service=provider).refresh(
            db,
            lead=lead,
            requested_by_user_id=user_id,
        )

        assert refreshed.workspace_id == workspace_id
        assert refreshed.website_domain == "acmedental.example"
        assert refreshed.has_website is True
        assert refreshed.review_count == 18
        assert refreshed.rating == 4.7
        assert refreshed.data_completeness > 0.45
        assert db.scalar(select(func.count(ProviderNormalizedFact.id))) == 2
        assert db.scalar(select(func.count(LeadScore.id))) == 1


def test_refresh_orchestrator_runs_web_validation_when_website_is_still_missing() -> None:
    session_factory = _build_session_factory()
    _, user_id, lead_id = _seed_refresh_target(session_factory)
    provider = _FakeRefreshProviderService(
        maps_place_payload={
            "place_results": {
                "title": "Acme Dental",
                "address": "Bagdat Avenue, Istanbul, Turkey",
                "phone": "+90 555 111 2233",
                "rating": 4.6,
                "reviews": 16,
                "gps_coordinates": {"latitude": 41.01, "longitude": 29.05},
                "data_id": "maps-acme-1",
                "type": "Dentist",
            }
        },
        web_payload={"knowledge_graph": {"website": "https://acmedental.example"}},
    )

    with session_factory() as db:
        lead = db.get(Lead, lead_id)
        assert lead is not None
        refreshed = LeadRefreshOrchestrator(provider_service=provider).refresh(
            db,
            lead=lead,
            requested_by_user_id=user_id,
        )

        assert refreshed.website_url == "https://acmedental.example"
        assert refreshed.website_domain == "acmedental.example"
        assert refreshed.has_website is True
        assert db.scalar(select(func.count(ProviderNormalizedFact.id))) == 3
        assert db.scalar(select(func.count(LeadScore.id))) == 1


def test_refresh_orchestrator_uses_demo_provider_runtime_when_forced(monkeypatch) -> None:
    monkeypatch.setenv("SERPAPI_API_KEY", "<replace-me>")
    monkeypatch.setenv("SERPAPI_RUNTIME_MODE", "demo")
    monkeypatch.setenv("ALLOW_DEMO_FALLBACKS", "false")
    clear_settings_cache()
    session_factory = _build_session_factory()
    _, user_id, lead_id = _seed_refresh_target(session_factory)

    try:
        with session_factory() as db:
            lead = db.get(Lead, lead_id)
            assert lead is not None
            refreshed = LeadRefreshOrchestrator().refresh(
                db,
                lead=lead,
                requested_by_user_id=user_id,
            )

            latest_fetch = db.scalar(
                select(ProviderFetch)
                .where(ProviderFetch.search_job_id == refreshed.search_job_id)
                .order_by(ProviderFetch.id.desc())
            )
            assert latest_fetch is not None
            assert latest_fetch.provider == "demo"
            assert refreshed.data_confidence > 0
    finally:
        clear_settings_cache()


def test_refresh_orchestrator_blocks_when_live_mode_is_forced_without_key(monkeypatch) -> None:
    monkeypatch.setenv("SERPAPI_API_KEY", "<replace-me>")
    monkeypatch.setenv("SERPAPI_RUNTIME_MODE", "live")
    monkeypatch.setenv("ALLOW_DEMO_FALLBACKS", "true")
    clear_settings_cache()
    session_factory = _build_session_factory()
    _, user_id, lead_id = _seed_refresh_target(session_factory)

    try:
        with session_factory() as db:
            lead = db.get(Lead, lead_id)
            assert lead is not None
            try:
                LeadRefreshOrchestrator().refresh(
                    db,
                    lead=lead,
                    requested_by_user_id=user_id,
                )
            except ServiceUnavailableError as exc:
                assert "Lead discovery is unavailable" in str(exc)
            else:
                raise AssertionError("Expected refresh to be blocked without a live SerpAPI key.")
    finally:
        clear_settings_cache()
