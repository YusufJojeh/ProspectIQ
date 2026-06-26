from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import clear_settings_cache
from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.modules.provider_serpapi.models import ProviderSettings
from app.modules.search_jobs.models import SearchJob, SearchRequest
from app.modules.search_jobs.schemas import SearchJobCreateRequest
from app.modules.users.models import Role, User, Workspace
from app.shared.enums.jobs import SearchJobStatus


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


def _seed_workspace_admin(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as db:
        db.add(Role(key="admin", label="Administrator"))
        db.commit()

        workspace = Workspace(public_id="ws_test", name="Test Workspace")
        db.add(workspace)
        db.commit()
        db.refresh(workspace)

        db.add(
            User(
                workspace_id=workspace.id,
                email="admin@example.com",
                full_name="Admin User",
                hashed_password=hash_password("AdminPass123"),
                role="admin",
            )
        )
        db.commit()


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
        json={
            "workspace": "ws_test",
            "email": "admin@example.com",
            "password": "AdminPass123",
        },
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_create_search_job_endpoint_persists_request_and_returns_status(monkeypatch) -> None:
    monkeypatch.setenv("SERPAPI_RUNTIME_MODE", "stub")
    clear_settings_cache()
    session_factory = _build_session_factory()
    _seed_workspace_admin(session_factory)
    monkeypatch.setattr(
        "app.modules.search_jobs.api.LeadDiscoveryOrchestrator.run",
        lambda self, job_public_id: None,
    )

    with _override_client(session_factory) as client:
        token = _login(client)
        create_response = client.post(
            "/api/v1/search-jobs",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "business_type": "Dentist",
                "city": "Istanbul",
                "region": "Kadikoy",
                "radius_km": 15,
                "max_results": 25,
                "min_rating": 4.0,
                "max_rating": 4.8,
                "min_reviews": 5,
                "max_reviews": 50,
                "website_preference": "must_have",
                "keyword_filter": "implant",
            },
        )

        assert create_response.status_code == 202
        payload = create_response.json()
        assert payload["discovery_runtime"] in {"live", "demo", "stub", "blocked"}
        assert payload["status"] == "queued"
        assert payload["radius_km"] == 15
        assert payload["website_preference"] == "must_have"
        assert payload["keyword_filter"] == "implant"

        status_response = client.get(
            f"/api/v1/search-jobs/{payload['public_id']}",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert status_response.status_code == 200
    assert status_response.json()["public_id"] == payload["public_id"]

    with session_factory() as db:
        search_request = db.scalar(
            select(SearchRequest).where(SearchRequest.keyword_filter == "implant")
        )
        assert search_request is not None
        assert search_request.website_preference == "must_have"
        assert search_request.radius_km == 15
        assert search_request.max_reviews == 50
    clear_settings_cache()
    monkeypatch.delenv("SERPAPI_RUNTIME_MODE", raising=False)


def test_create_search_job_endpoint_rejects_invalid_filter_ranges(monkeypatch) -> None:
    session_factory = _build_session_factory()
    _seed_workspace_admin(session_factory)
    monkeypatch.setattr(
        "app.modules.search_jobs.api.LeadDiscoveryOrchestrator.run",
        lambda self, job_public_id: None,
    )

    with _override_client(session_factory) as client:
        token = _login(client)
        response = client.post(
            "/api/v1/search-jobs",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "business_type": "Dentist",
                "city": "Istanbul",
                "max_results": 25,
                "min_rating": 4.8,
                "max_rating": 4.0,
                "website_preference": "any",
            },
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation.invalid_payload"


def test_create_search_job_endpoint_returns_503_when_discovery_is_blocked(monkeypatch) -> None:
    monkeypatch.setenv("SERPAPI_API_KEY", "")
    monkeypatch.setenv("SERPAPI_RUNTIME_MODE", "blocked")
    clear_settings_cache()
    session_factory = _build_session_factory()
    _seed_workspace_admin(session_factory)
    monkeypatch.setattr(
        "app.modules.search_jobs.api.LeadDiscoveryOrchestrator.run",
        lambda self, job_public_id: None,
    )

    with _override_client(session_factory) as client:
        token = _login(client)
        response = client.post(
            "/api/v1/search-jobs",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "business_type": "Dentist",
                "city": "Istanbul",
                "max_results": 25,
                "website_preference": "any",
            },
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] in {"service_unavailable", "provider.unavailable"}
    clear_settings_cache()
    monkeypatch.delenv("SERPAPI_RUNTIME_MODE", raising=False)


async def _fake_arabic_prompt_parse(_self: object, _prompt: str) -> SearchJobCreateRequest:
    return SearchJobCreateRequest(
        business_type="\u0635\u0627\u0644\u0648\u0646\u0627\u062a \u062a\u062c\u0645\u064a\u0644",
        city="\u062c\u062f\u0629",
        max_results=25,
    )


def test_create_search_job_from_arabic_prompt_sets_provider_locale(monkeypatch) -> None:
    monkeypatch.setenv("SERPAPI_RUNTIME_MODE", "stub")
    clear_settings_cache()
    session_factory = _build_session_factory()
    _seed_workspace_admin(session_factory)
    monkeypatch.setattr(
        "app.modules.search_jobs.prompt_parser.SearchPromptParser.parse",
        _fake_arabic_prompt_parse,
    )
    monkeypatch.setattr(
        "app.modules.search_jobs.api.LeadDiscoveryOrchestrator.run",
        lambda self, job_public_id: None,
    )

    with _override_client(session_factory) as client:
        token = _login(client)
        response = client.post(
            "/api/v1/search-jobs/from-prompt",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "prompt": (
                    "\u0627\u0628\u062d\u062b \u0639\u0646 "
                    "\u0635\u0627\u0644\u0648\u0646\u0627\u062a "
                    "\u062a\u062c\u0645\u064a\u0644 "
                    "\u0641\u064a \u062c\u062f\u0629 "
                    "\u0628\u062f\u0648\u0646 \u0645\u0648\u0642\u0639"
                )
            },
        )

    assert response.status_code == 202
    with session_factory() as db:
        workspace = db.scalar(select(Workspace).where(Workspace.public_id == "ws_test"))
        assert workspace is not None
        provider_settings = db.scalar(
            select(ProviderSettings).where(ProviderSettings.workspace_id == workspace.id)
        )

    assert provider_settings is not None
    assert provider_settings.hl == "ar"
    assert provider_settings.gl == "sa"

    clear_settings_cache()
    monkeypatch.delenv("SERPAPI_RUNTIME_MODE", raising=False)


def test_list_search_jobs_auto_requeues_stale_running_job(monkeypatch) -> None:
    monkeypatch.setenv("SERPAPI_RUNTIME_MODE", "stub")
    monkeypatch.setenv("DISCOVERY_STALE_JOB_SECONDS", "60")
    monkeypatch.setenv("DISCOVERY_GLOBAL_JOB_DEADLINE_SECONDS", "60")
    clear_settings_cache()
    session_factory = _build_session_factory()
    _seed_workspace_admin(session_factory)
    requeued_ids: list[str] = []
    monkeypatch.setattr(
        "app.modules.search_jobs.api.LeadDiscoveryOrchestrator.run",
        lambda self, job_public_id: requeued_ids.append(job_public_id),
    )

    with session_factory() as db:
        workspace = db.scalar(select(Workspace).where(Workspace.public_id == "ws_test"))
        user = db.scalar(select(User).where(User.email == "admin@example.com"))
        assert workspace is not None
        assert user is not None
        stale_started_at = datetime.now(tz=UTC) - timedelta(minutes=30)
        job = SearchJob(
            workspace_id=workspace.id,
            requested_by_user_id=user.id,
            business_type="Marketing Agency",
            city="Dubai",
            max_results=20,
            website_preference="any",
            status=SearchJobStatus.RUNNING.value,
            queued_at=stale_started_at,
            started_at=stale_started_at,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        job_public_id = job.public_id

    with _override_client(session_factory) as client:
        token = _login(client)
        response = client.get(
            "/api/v1/search-jobs",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    payload = response.json()["items"][0]
    assert payload["public_id"] == job_public_id
    assert payload["status"] == "queued"
    assert requeued_ids == [job_public_id]

    with session_factory() as db:
        saved = db.scalar(select(SearchJob).where(SearchJob.public_id == job_public_id))
        assert saved is not None
        assert saved.status == SearchJobStatus.QUEUED.value
        assert saved.started_at is None

    clear_settings_cache()
    monkeypatch.delenv("SERPAPI_RUNTIME_MODE", raising=False)
    monkeypatch.delenv("DISCOVERY_STALE_JOB_SECONDS", raising=False)
    monkeypatch.delenv("DISCOVERY_GLOBAL_JOB_DEADLINE_SECONDS", raising=False)
