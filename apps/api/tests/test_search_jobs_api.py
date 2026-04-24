from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import clear_settings_cache
from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.modules.search_jobs.models import SearchRequest
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
        assert payload["discovery_runtime"] in {"demo", "serpapi", "blocked"}
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
    assert response.json()["error"]["code"] == "validation_error"


def test_create_search_job_endpoint_returns_503_when_discovery_is_blocked(monkeypatch) -> None:
    monkeypatch.setenv("SERPAPI_API_KEY", "<replace-me>")
    monkeypatch.setenv("SERPAPI_RUNTIME_MODE", "live")
    monkeypatch.setenv("ALLOW_DEMO_FALLBACKS", "false")
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
    assert response.json()["error"]["code"] == "service_unavailable"
    clear_settings_cache()
