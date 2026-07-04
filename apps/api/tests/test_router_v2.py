"""Tests for /api/v2 endpoints (router_v2.py).

Covers:
  - POST /api/v2/search — locale resolution (lang=ar, lang=en, auto_detect)
  - GET  /api/v2/stream/{job_id}  — terminal-job SSE
  - GET  /api/v2/results/{job_id} — paginated V2Lead response
  - GET  /api/v2/export/{job_id}?format=csv|json — file downloads
"""
from __future__ import annotations

import pytest
from sqlalchemy import select
from test_workspace_e2e import _build_session_factory, _login, _override_client, _seed_workspace

from app.modules.provider_serpapi.models import ProviderSettings
from app.modules.search_jobs.models import SearchJob
from app.modules.search_jobs.schemas import SearchJobCreateRequest
from app.modules.users.models import Workspace

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FIXED_JOB_REQUEST = SearchJobCreateRequest(
    business_type="Dental Clinic",
    city="Dubai",
    max_results=25,
)


async def _fake_parse(_self: object, _prompt: str) -> SearchJobCreateRequest:
    return _FIXED_JOB_REQUEST


def _get_search_job_public_id(session_factory, seed) -> str:
    with session_factory() as db:
        workspace = db.scalar(
            select(Workspace).where(Workspace.public_id == seed.workspace_public_id)
        )
        assert workspace is not None
        job = db.scalar(
            select(SearchJob).where(SearchJob.workspace_id == workspace.id)
        )
        assert job is not None
        return str(job.public_id)


def _get_provider_settings(session_factory, seed) -> ProviderSettings | None:
    with session_factory() as db:
        workspace = db.scalar(
            select(Workspace).where(Workspace.public_id == seed.workspace_public_id)
        )
        assert workspace is not None
        return db.scalar(
            select(ProviderSettings).where(ProviderSettings.workspace_id == workspace.id)
        )


# ---------------------------------------------------------------------------
# POST /api/v2/search — locale resolution
# ---------------------------------------------------------------------------


def test_post_v2_search_lang_ar_sets_arabic_locale(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SERPAPI_RUNTIME_MODE", "stub")
    from app.core.config import clear_settings_cache
    clear_settings_cache()

    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    monkeypatch.setattr(
        "app.modules.search_jobs.prompt_parser.SearchPromptParser.parse", _fake_parse
    )
    monkeypatch.setattr(
        "app.modules.search_jobs.router_v2.LeadDiscoveryOrchestrator.run",
        lambda self, job_public_id: None,
    )

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = client.post(
            "/api/v2/search",
            headers={"Authorization": f"Bearer {token}"},
            json={"query": "dental clinics in Dubai", "lang": "ar", "auto_detect": False},
        )

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "queued"
    assert data["job_id"].startswith("job_")

    settings = _get_provider_settings(session_factory, seed)
    assert settings is not None
    assert settings.hl == "ar"
    assert settings.gl == "sa"


def test_post_v2_search_lang_en_sets_english_locale(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SERPAPI_RUNTIME_MODE", "stub")
    from app.core.config import clear_settings_cache
    clear_settings_cache()

    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    monkeypatch.setattr(
        "app.modules.search_jobs.prompt_parser.SearchPromptParser.parse", _fake_parse
    )
    monkeypatch.setattr(
        "app.modules.search_jobs.router_v2.LeadDiscoveryOrchestrator.run",
        lambda self, job_public_id: None,
    )

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = client.post(
            "/api/v2/search",
            headers={"Authorization": f"Bearer {token}"},
            json={"query": "dental clinics in Dubai", "lang": "en", "auto_detect": False},
        )

    assert response.status_code == 202
    settings = _get_provider_settings(session_factory, seed)
    assert settings is not None
    assert settings.hl == "en"
    assert settings.gl == "us"


def test_post_v2_search_auto_detect_arabic_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SERPAPI_RUNTIME_MODE", "stub")
    from app.core.config import clear_settings_cache
    clear_settings_cache()

    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    monkeypatch.setattr(
        "app.modules.search_jobs.prompt_parser.SearchPromptParser.parse", _fake_parse
    )
    monkeypatch.setattr(
        "app.modules.search_jobs.router_v2.LeadDiscoveryOrchestrator.run",
        lambda self, job_public_id: None,
    )

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = client.post(
            "/api/v2/search",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept-Language": "ar-SA,ar;q=0.9,en;q=0.8",
            },
            json={"query": "dental clinics in Dubai", "lang": "en", "auto_detect": True},
        )

    assert response.status_code == 202
    settings = _get_provider_settings(session_factory, seed)
    assert settings is not None
    assert settings.hl == "ar"
    assert settings.gl == "sa"


def test_post_v2_search_auto_detect_english_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SERPAPI_RUNTIME_MODE", "stub")
    from app.core.config import clear_settings_cache
    clear_settings_cache()

    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    monkeypatch.setattr(
        "app.modules.search_jobs.prompt_parser.SearchPromptParser.parse", _fake_parse
    )
    monkeypatch.setattr(
        "app.modules.search_jobs.router_v2.LeadDiscoveryOrchestrator.run",
        lambda self, job_public_id: None,
    )

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = client.post(
            "/api/v2/search",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept-Language": "en-US,en;q=0.9",
            },
            json={"query": "dental clinics in Dubai", "lang": "ar", "auto_detect": True},
        )

    assert response.status_code == 202
    settings = _get_provider_settings(session_factory, seed)
    assert settings is not None
    assert settings.hl == "en"
    assert settings.gl == "us"


# ---------------------------------------------------------------------------
# GET /api/v2/stream/{job_id}
# ---------------------------------------------------------------------------


def test_get_v2_stream_terminal_job_returns_done_event(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SERPAPI_RUNTIME_MODE", "stub")
    from app.core.config import clear_settings_cache
    clear_settings_cache()

    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    job_id = _get_search_job_public_id(session_factory, seed)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = client.get(
            f"/api/v2/stream/{job_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")
    text = response.text
    assert "data:" in text
    assert '"stage": "done"' in text


# ---------------------------------------------------------------------------
# GET /api/v2/results/{job_id}
# ---------------------------------------------------------------------------


def test_get_v2_results_returns_v2_lead_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SERPAPI_RUNTIME_MODE", "stub")
    from app.core.config import clear_settings_cache
    clear_settings_cache()

    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    job_id = _get_search_job_public_id(session_factory, seed)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = client.get(
            f"/api/v2/results/{job_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "page" in data
    assert "per_page" in data
    assert "total" in data
    assert data["page"] == 1
    # Seeded workspace has exactly 1 lead for this job.
    assert data["total"] == 1
    lead = data["items"][0]
    assert "company" in lead
    assert "email" in lead
    assert "linkedin_url" in lead
    assert "industry" in lead
    assert "ai_opener" in lead
    assert "logo_url" in lead
    assert lead["company"] == "Acme Dental"


# ---------------------------------------------------------------------------
# GET /api/v2/export/{job_id}?format=csv|json
# ---------------------------------------------------------------------------


def test_get_v2_export_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SERPAPI_RUNTIME_MODE", "stub")
    from app.core.config import clear_settings_cache
    clear_settings_cache()

    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    job_id = _get_search_job_public_id(session_factory, seed)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = client.get(
            f"/api/v2/export/{job_id}?format=csv",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert "text/csv" in response.headers.get("content-type", "")
    assert "Acme Dental" in response.text


def test_get_v2_export_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SERPAPI_RUNTIME_MODE", "stub")
    from app.core.config import clear_settings_cache
    clear_settings_cache()

    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    job_id = _get_search_job_public_id(session_factory, seed)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = client.get(
            f"/api/v2/export/{job_id}?format=json",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    import json
    data = json.loads(response.text)
    assert "items" in data
    assert any(item.get("business_name") == "Acme Dental" for item in data["items"])
