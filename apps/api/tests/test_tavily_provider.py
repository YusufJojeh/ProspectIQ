from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import Settings, clear_settings_cache
from app.modules.provider_tavily.client import TavilyClient
from app.modules.provider_tavily.demo_service import DemoTavilyService
from app.modules.provider_tavily.engines.tavily_web import build_tavily_web_params
from app.modules.provider_tavily.normalizers.tavily_lead_normalizer import (
    TavilyLeadDiscoveryNormalizer,
)
from app.modules.provider_tavily.normalizers.tavily_web_normalizer import TavilyWebNormalizer


@dataclass
class _FakeResponse:
    status_code: int
    headers: dict[str, str]


class _FakeTavilyError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        retry_after: str | None = None,
    ) -> None:
        self.response = _FakeResponse(
            status_code=status_code,
            headers={"retry-after": retry_after} if retry_after else {},
        )
        super().__init__(message)


class _FakeSdkClient:
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def search(self, **kwargs: Any) -> object:
        self.calls.append(("search", kwargs))
        return self._next()

    def extract(self, **kwargs: Any) -> object:
        self.calls.append(("extract", kwargs))
        return self._next()

    def research(self, **kwargs: Any) -> object:
        self.calls.append(("research", kwargs))
        return self._next()

    def get_research(self, request_id: str, **kwargs: Any) -> object:
        self.calls.append(("get_research", {"request_id": request_id, **kwargs}))
        return self._next()

    def _next(self) -> object:
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


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


def test_tavily_lead_normalizer_dedupes_domains_and_preserves_evidence() -> None:
    normalizer = TavilyLeadDiscoveryNormalizer()
    candidates = normalizer.normalize(
        {
            "results": [
                {
                    "title": "Acme Dental - Official Website",
                    "url": "https://acmedental.example",
                    "content": "Acme Dental provides local dental services.",
                    "score": 0.92,
                },
                {
                    "title": "Acme Dental Contact",
                    "url": "https://acmedental.example/contact",
                    "content": "Duplicate domain.",
                    "score": 0.88,
                },
                {
                    "title": "Directory listing",
                    "url": "https://www.yelp.com/biz/acme-dental",
                    "content": "Directory listing.",
                    "score": 0.5,
                },
            ]
        },
        business_type="Dentist",
        city="Istanbul",
        query="Dentist Istanbul official",
        extracted_by_url={"https://acmedental.example": "Extracted official content."},
    )

    assert len(candidates) == 1
    assert candidates[0].company_name == "Acme Dental"
    assert candidates[0].website_domain == "acmedental.example"
    assert candidates[0].facts["source_type"] == "tavily_search"
    assert candidates[0].facts["extracted_content"] == "Extracted official content."
    evidence = candidates[0].facts["evidence"]
    assert isinstance(evidence, dict)
    assert evidence["provider"] == "tavily"
    assert evidence["url"] == "https://acmedental.example"


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
        extract_fetch, extract_payload = service.extract_urls(
            db,
            workspace_id=workspace.id,
            search_job_id=None,
            urls=["https://acmedental.example"],
            query="Acme Dental",
        )

        assert fetch.provider == "tavily"
        assert fetch.status == "ok"
        assert payload["results"]
        assert payload["answer"]
        assert extract_fetch.mode == "extract"
        assert extract_payload["results"]


def test_tavily_client_retries_rate_limit_retry_after_then_succeeds(monkeypatch) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "test-tavily-key")
    clear_settings_cache()
    sleeps: list[float] = []
    sdk = _FakeSdkClient(
        [
            _FakeTavilyError("rate limit exceeded", status_code=429, retry_after="2"),
            {
                "query": "Acme Dental",
                "answer": "Acme Dental is a clinic in Istanbul.",
                "results": [{"url": "https://acmedental.example", "score": 0.9}],
                "request_id": "tvly-1",
            },
        ]
    )

    try:
        client = TavilyClient(sdk_client=sdk, sleep_fn=sleeps.append)
        result = client.search({"query": "Acme Dental"})
    finally:
        clear_settings_cache()

    assert [call[0] for call in sdk.calls] == ["search", "search"]
    assert sleeps == [2.0]
    assert result.ok is True
    assert result.tavily_request_id == "tvly-1"
    assert result.payload is not None
    assert result.payload["answer"].startswith("Acme Dental")


def test_tavily_client_fails_closed_on_auth_error(monkeypatch) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "test-tavily-key")
    clear_settings_cache()
    sdk = _FakeSdkClient(
        [
            _FakeTavilyError(
                "unauthorized for key test-tavily-key",
                status_code=401,
            )
        ]
    )

    try:
        result = TavilyClient(sdk_client=sdk).search({"query": "Acme Dental"})
    finally:
        clear_settings_cache()

    assert result.ok is False
    assert result.status_code == 401
    assert result.error_message == "unauthorized for key [REDACTED]"


def test_tavily_client_fails_closed_on_unexpected_payload(monkeypatch) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "test-tavily-key")
    clear_settings_cache()
    sdk = _FakeSdkClient(["not-json-like"])

    try:
        result = TavilyClient(sdk_client=sdk).search({"query": "Acme Dental"})
    finally:
        clear_settings_cache()

    assert result.ok is False
    assert result.status_code is None
    assert result.error_message == "Tavily returned an unexpected payload shape."


def test_tavily_runtime_defaults_to_blocked_without_key() -> None:
    settings = Settings(
        _env_file=None,
        app_env="development",
        tavily_api_key="",
        tavily_runtime_mode_override=None,
    )

    assert settings.has_tavily_configured is False
    assert settings.tavily_runtime == "blocked"
