from __future__ import annotations

import httpx

from app.core.config import clear_settings_cache
from app.modules.provider_tavily.client import TavilyClient
from app.modules.provider_tavily.demo_service import DemoTavilyService
from app.modules.provider_tavily.engines.tavily_web import build_tavily_web_params
from app.modules.provider_tavily.normalizers.tavily_web_normalizer import TavilyWebNormalizer


def test_tavily_web_params_normalize_whitespace_and_limit_query_length() -> None:
    params = build_tavily_web_params(query="  Acme   Dental   official website  ", max_results=50)

    assert params["query"] == "Acme Dental official website"
    assert params["max_results"] == 20
    assert params["search_depth"] == "basic"
    assert params["include_answer"] is True


def test_tavily_web_params_reject_empty_query() -> None:
    try:
        build_tavily_web_params(query="   ")
    except ValueError as exc:
        assert "query must not be empty" in str(exc)
    else:
        raise AssertionError("Expected empty Tavily query to fail closed.")


def test_tavily_web_normalizer_skips_directory_domains_and_uses_business_domain() -> None:
    result = TavilyWebNormalizer().normalize(
        {
            "answer": "Acme Dental is a local dental clinic.",
            "results": [
                {"url": "https://www.facebook.com/acme-dental", "score": 0.6},
                {"url": "https://acmedental.example/contact", "score": 0.91},
            ],
        }
    )

    assert result.website_url == "https://acmedental.example/contact"
    assert result.website_domain == "acmedental.example"
    assert result.facts["source"] == "tavily"
    assert result.facts["directory_results_before_official"] == 1
    assert result.facts["answer_present"] is True
    assert result.facts["result_count"] == 2


def test_tavily_web_normalizer_reports_no_official_site_when_only_directories_present() -> None:
    result = TavilyWebNormalizer().normalize(
        {
            "answer": None,
            "results": [
                {"url": "https://www.yelp.com/biz/acme-dental", "score": 0.5},
            ],
        }
    )

    assert result.website_url is None
    assert result.website_domain is None
    assert result.confidence == 0.0
    assert result.facts["official_site_found"] is False
    assert result.facts["answer_present"] is False


def test_demo_tavily_service_persists_provider_fetch_and_raw_payload() -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session, sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.core.database import Base
    from app.modules.users.models import Workspace

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session
    )

    service = DemoTavilyService()
    with session_factory() as db:
        workspace = Workspace(name="LeadScope Workspace")
        db.add(workspace)
        db.commit()
        db.refresh(workspace)

        fetch, payload = service.web_search(
            db, workspace_id=workspace.id, search_job_id=None, query="Acme Dental Istanbul"
        )

        assert fetch.provider == "tavily"
        assert fetch.status == "ok"
        assert payload["results"]
        assert payload["answer"]


def test_tavily_client_retries_rate_limit_then_succeeds(monkeypatch) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "test-tavily-key")
    clear_settings_cache()
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(429, json={"error": "rate limit exceeded"})
        return httpx.Response(
            200,
            json={
                "query": "Acme Dental",
                "answer": "Acme Dental is a clinic in Istanbul.",
                "results": [{"url": "https://acmedental.example", "score": 0.9}],
            },
        )

    client = TavilyClient()
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        result = client.search({"query": "Acme Dental"})
    finally:
        client._client.close()
        clear_settings_cache()

    assert calls["count"] == 2
    assert result.ok is True
    assert result.payload is not None
    assert result.payload["answer"].startswith("Acme Dental")


def test_tavily_client_fails_closed_on_non_json_success_response(monkeypatch) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "test-tavily-key")
    clear_settings_cache()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text="<html>temporary edge page</html>",
            headers={"content-type": "text/html"},
        )

    client = TavilyClient()
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        result = client.search({"query": "Acme Dental"})
    finally:
        client._client.close()
        clear_settings_cache()

    assert result.ok is False
    assert result.status_code == 200
    assert result.error_message == "Tavily returned a non-JSON response."


def test_tavily_runtime_defaults_to_blocked_without_key(monkeypatch) -> None:
    from app.core.config import get_settings

    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    clear_settings_cache()
    try:
        settings = get_settings()
        assert settings.has_tavily_configured is False
        assert settings.tavily_runtime == "blocked"
    finally:
        clear_settings_cache()
