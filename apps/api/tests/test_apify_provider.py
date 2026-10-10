from __future__ import annotations

from datetime import UTC, datetime

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import clear_settings_cache
from app.core.database import Base
from app.modules.leads.models import Lead  # noqa: F401
from app.modules.provider_apify.allowlist import resolve_actor_id
from app.modules.provider_apify.client import ApifyCallResult, ApifyClient, _actor_path
from app.modules.provider_apify.demo_service import DemoApifyService
from app.modules.provider_apify.exceptions import ProviderConfigError, UnknownActorError
from app.modules.provider_apify.normalizers.apify_normalizer import ApifyCrawlNormalizer
from app.modules.provider_apify.service import ApifyService
from app.modules.provider_serpapi.models import ProviderFetch
from app.modules.search_jobs.models import SearchJob  # noqa: F401
from app.modules.users.models import Workspace


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


def test_actor_path_converts_owner_slash_name_to_tilde() -> None:
    assert _actor_path("apify/website-content-crawler") == "apify~website-content-crawler"
    assert _actor_path(" apify/website-content-crawler ") == "apify~website-content-crawler"


def test_allowlist_resolves_default_company_website_crawler_and_rejects_unknown_key() -> None:
    clear_settings_cache()
    try:
        assert resolve_actor_id("company_website_crawler") == "apify/website-content-crawler"
        assert resolve_actor_id("business_directory_crawler") is None
        assert resolve_actor_id("not_a_real_key") is None
    finally:
        clear_settings_cache()


def test_apify_client_init_raises_without_token(monkeypatch) -> None:
    monkeypatch.setenv("APIFY_API_TOKEN", "")
    clear_settings_cache()
    try:
        try:
            ApifyClient()
        except ProviderConfigError as exc:
            assert "APIFY_API_TOKEN" in str(exc)
        else:
            raise AssertionError("Expected ApifyClient to fail closed without a token.")
    finally:
        clear_settings_cache()


def test_apify_client_retries_rate_limited_dataset_fetch_then_succeeds(monkeypatch) -> None:
    monkeypatch.setenv("APIFY_API_TOKEN", "test-apify-token")
    clear_settings_cache()
    monkeypatch.setattr("app.modules.provider_apify.client.time.sleep", lambda _seconds: None)
    calls = {"start": 0, "dataset": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/runs"):
            calls["start"] += 1
            return httpx.Response(
                201,
                json={
                    "data": {
                        "id": f"run-{calls['start']}",
                        "status": "SUCCEEDED",
                        "defaultDatasetId": "dataset-1",
                    }
                },
            )
        if "/datasets/" in request.url.path:
            calls["dataset"] += 1
            if calls["dataset"] == 1:
                return httpx.Response(429, json={"error": "rate limited"})
            return httpx.Response(
                200,
                json=[{"url": "https://acmedental.example", "phone": "+1 555 0100"}],
            )
        raise AssertionError(f"Unexpected request path: {request.url.path}")

    try:
        client = ApifyClient()
        client._client = httpx.Client(
            base_url="https://api.apify.com/v2", transport=httpx.MockTransport(handler)
        )
        result = client.run_actor_and_get_items(
            "apify/website-content-crawler", {"startUrls": [{"url": "https://acmedental.example"}]}
        )
    finally:
        client._client.close()
        clear_settings_cache()

    assert calls["start"] == 2
    assert calls["dataset"] == 2
    assert result.ok is True
    assert result.apify_run_id == "run-2"
    assert result.payload is not None
    assert result.payload["items"] == [
        {"url": "https://acmedental.example", "phone": "+1 555 0100"}
    ]


def test_apify_client_fails_closed_on_hard_error_without_retry(monkeypatch) -> None:
    monkeypatch.setenv("APIFY_API_TOKEN", "test-apify-token")
    clear_settings_cache()
    monkeypatch.setattr("app.modules.provider_apify.client.time.sleep", lambda _seconds: None)
    calls = {"start": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["start"] += 1
        return httpx.Response(403, json={"error": "forbidden"})

    try:
        client = ApifyClient()
        client._client = httpx.Client(
            base_url="https://api.apify.com/v2", transport=httpx.MockTransport(handler)
        )
        result = client.run_actor_and_get_items(
            "apify/website-content-crawler", {"startUrls": [{"url": "https://acmedental.example"}]}
        )
    finally:
        client._client.close()
        clear_settings_cache()

    assert calls["start"] == 1
    assert result.ok is False
    assert result.apify_run_id is None
    assert result.error_message == "Apify run request failed with HTTP 403."


def test_apify_service_raises_unknown_actor_before_persisting_any_fetch() -> None:
    session_factory = _build_session_factory()
    with session_factory() as db:
        workspace = Workspace(name="LeadScope Workspace")
        db.add(workspace)
        db.commit()
        db.refresh(workspace)

        service = ApifyService()
        try:
            service.crawl(
                db,
                workspace_id=workspace.id,
                search_job_id=None,
                actor_key="not_a_real_key",
                run_input={},
            )
        except UnknownActorError:
            pass
        else:
            raise AssertionError("Expected UnknownActorError for a non-allowlisted actor key.")

        assert db.query(ProviderFetch).count() == 0


class _FakeApifyClient:
    def __init__(self, result: ApifyCallResult) -> None:
        self._result = result

    def run_actor_and_get_items(self, actor_id: str, run_input: dict, *, max_attempts: int = 2):
        self.actor_id = actor_id
        self.run_input = run_input
        return self._result


def test_apify_service_crawl_persists_fetch_and_raw_payload_on_success() -> None:
    session_factory = _build_session_factory()
    with session_factory() as db:
        workspace = Workspace(name="LeadScope Workspace")
        db.add(workspace)
        db.commit()
        db.refresh(workspace)

        now = datetime.now(tz=UTC)
        fake_result = ApifyCallResult(
            ok=True,
            status_code=201,
            payload={
                "items": [{"url": "https://acmedental.example", "phone": "+1 555 0100"}],
                "item_count": 1,
                "run_status": "SUCCEEDED",
                "apify_run_id": "run-42",
            },
            error_message=None,
            apify_run_id="run-42",
            started_at=now,
            finished_at=now,
        )
        service = ApifyService(client=_FakeApifyClient(fake_result))
        fetch, payload = service.crawl(
            db,
            workspace_id=workspace.id,
            search_job_id=None,
            actor_key="company_website_crawler",
            run_input={"startUrls": [{"url": "https://acmedental.example"}]},
        )

        assert fetch.provider == "apify"
        assert fetch.engine == "company_website_crawler"
        assert fetch.status == "ok"
        assert fetch.serpapi_search_id == "run-42"
        assert payload["items"][0]["url"] == "https://acmedental.example"
        assert db.query(ProviderFetch).count() == 1


def test_demo_apify_service_persists_fetch_and_rejects_unknown_actor() -> None:
    session_factory = _build_session_factory()
    with session_factory() as db:
        workspace = Workspace(name="LeadScope Workspace")
        db.add(workspace)
        db.commit()
        db.refresh(workspace)

        service = DemoApifyService()
        try:
            service.crawl(
                db,
                workspace_id=workspace.id,
                search_job_id=None,
                actor_key="not_a_real_key",
                run_input={},
            )
        except UnknownActorError:
            pass
        else:
            raise AssertionError("Expected UnknownActorError for a non-allowlisted actor key.")

        fetch, payload = service.crawl(
            db,
            workspace_id=workspace.id,
            search_job_id=None,
            actor_key="company_website_crawler",
            run_input={"startUrls": [{"url": "https://acmedental.example"}]},
        )

        assert fetch.provider == "apify"
        assert fetch.status == "ok"
        assert fetch.serpapi_search_id == payload["apify_run_id"]
        assert payload["items"][0]["url"] == "https://acmedental.example"


def test_apify_normalizer_extracts_phone_from_free_text_and_computes_domain() -> None:
    normalized = ApifyCrawlNormalizer().normalize(
        {
            "items": [
                {
                    "url": "https://acmedental.example/contact",
                    "title": "Acme Dental",
                    "text": "Visit us or call +1 555 0100 for an appointment.",
                    "category": "Dentist",
                },
                {"unrelated": "no usable fields here"},
            ]
        },
        actor_key="company_website_crawler",
        fallback_company_name="Fallback Co",
    )

    assert len(normalized) == 1
    fact = normalized[0]
    assert fact["company_name"] == "Acme Dental"
    assert fact["website_domain"] == "acmedental.example"
    assert fact["phone"] is not None
    assert fact["facts"]["actor_key"] == "company_website_crawler"


def test_apify_normalizer_falls_back_to_company_name_and_skips_empty_items() -> None:
    normalized = ApifyCrawlNormalizer().normalize(
        {"items": [{"phone": "+1 555 0100"}]},
        actor_key="company_website_crawler",
        fallback_company_name="Fallback Co",
    )

    assert len(normalized) == 1
    assert normalized[0]["company_name"] == "Fallback Co"
    assert normalized[0]["website_url"] is None
