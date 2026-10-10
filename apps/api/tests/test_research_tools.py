from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import clear_settings_cache
from app.core.database import Base
from app.modules.leads.models import Lead
from app.modules.provider_serpapi.models import ProviderFetch, ProviderNormalizedFact
from app.modules.research.tools import TOOL_DEFINITIONS, ResearchToolExecutor
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


def _make_workspace_and_lead(db: Session, *, website_url: str | None = None) -> tuple[int, Lead]:
    workspace = Workspace(name="LeadScope Workspace")
    db.add(workspace)
    db.commit()
    db.refresh(workspace)

    lead = Lead(
        workspace_id=workspace.id,
        company_name="Acme Dental",
        city="Springfield",
        category="Dentist",
        website_url=website_url,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return workspace.id, lead


# --- Security invariant: no tool schema can carry a URL or Actor ID --------


def test_no_tool_definition_exposes_a_url_or_actor_id_parameter() -> None:
    forbidden_fragments = ("url", "actor", "actor_id", "domain")
    for spec in TOOL_DEFINITIONS:
        if spec.name == "resolve_company_domain":
            # The only tool allowed a `url` field: pure string parsing of an
            # already-discovered URL, never a fetch target (see module docstring).
            continue
        properties = spec.parameters.get("properties", {})
        for param_name in properties:
            for fragment in forbidden_fragments:
                assert fragment not in param_name.lower(), (
                    f"{spec.name} exposes a '{param_name}' parameter; crawl/actor targets "
                    "must be resolved server-side, never supplied by the LLM."
                )


def test_crawl_tool_definitions_take_no_parameters_at_all() -> None:
    for name in ("crawl_company_site", "crawl_reviews"):
        spec = next(spec for spec in TOOL_DEFINITIONS if spec.name == name)
        assert spec.parameters["properties"] == {}


# --- ResearchToolExecutor ----------------------------------------------------


def test_resolve_company_domain_extracts_domain_without_network_call() -> None:
    session_factory = _build_session_factory()
    with session_factory() as db:
        _, lead = _make_workspace_and_lead(db)
        executor = ResearchToolExecutor(db, workspace_id=lead.workspace_id, lead=lead)

        result = executor.execute("resolve_company_domain", {"url": "https://www.Acme.example/x"})

        assert result == {"domain": "acme.example"}


def test_resolve_company_domain_requires_a_url_argument() -> None:
    session_factory = _build_session_factory()
    with session_factory() as db:
        _, lead = _make_workspace_and_lead(db)
        executor = ResearchToolExecutor(db, workspace_id=lead.workspace_id, lead=lead)

        result = executor.execute("resolve_company_domain", {})

        assert "error" in result


def test_crawl_company_site_fails_closed_without_a_known_website() -> None:
    session_factory = _build_session_factory()
    with session_factory() as db:
        _, lead = _make_workspace_and_lead(db, website_url=None)
        executor = ResearchToolExecutor(db, workspace_id=lead.workspace_id, lead=lead)

        result = executor.execute("crawl_company_site", {})

        assert result["ok"] is False
        assert executor.crawls_performed == 0


def test_crawl_reviews_fails_closed_without_a_place_identity() -> None:
    session_factory = _build_session_factory()
    with session_factory() as db:
        _, lead = _make_workspace_and_lead(db)
        executor = ResearchToolExecutor(db, workspace_id=lead.workspace_id, lead=lead)

        result = executor.execute("crawl_reviews", {})

        assert result["ok"] is False
        assert executor.crawls_performed == 0


def test_execute_unknown_tool_returns_error_without_raising() -> None:
    session_factory = _build_session_factory()
    with session_factory() as db:
        _, lead = _make_workspace_and_lead(db)
        executor = ResearchToolExecutor(db, workspace_id=lead.workspace_id, lead=lead)

        result = executor.execute("delete_everything", {})

        assert "error" in result


def test_search_web_tavily_persists_fact_and_updates_known_website(monkeypatch) -> None:
    monkeypatch.setenv("TAVILY_RUNTIME_MODE", "demo")
    clear_settings_cache()
    try:
        session_factory = _build_session_factory()
        with session_factory() as db:
            _, lead = _make_workspace_and_lead(db, website_url=None)
            executor = ResearchToolExecutor(db, workspace_id=lead.workspace_id, lead=lead)

            result = executor.execute("search_web_tavily", {})

            assert result["ok"] is True
            assert executor.searches_performed == 1
            assert db.query(ProviderFetch).count() == 1
    finally:
        clear_settings_cache()


def test_get_existing_evidence_returns_previously_persisted_facts() -> None:
    session_factory = _build_session_factory()
    with session_factory() as db:
        _, lead = _make_workspace_and_lead(db)
        fetch = ProviderFetch(
            workspace_id=lead.workspace_id,
            provider="tavily",
            engine="web_search",
            mode="research",
            request_fingerprint="fp-1",
            request_params_json={},
            status="ok",
        )
        db.add(fetch)
        db.commit()
        db.refresh(fetch)
        db.add(
            ProviderNormalizedFact(
                workspace_id=lead.workspace_id,
                lead_id=lead.id,
                provider_fetch_id=fetch.id,
                source_type="tavily_research",
                company_name="Acme Dental",
                phone="+15550100",
                confidence=0.6,
            )
        )
        db.commit()

        executor = ResearchToolExecutor(db, workspace_id=lead.workspace_id, lead=lead)
        result = executor.execute("get_existing_evidence", {})

        assert result["count"] == 1
        assert result["facts"][0]["phone"] == "+15550100"


def test_compare_evidence_returns_evidence_graph_shape() -> None:
    session_factory = _build_session_factory()
    with session_factory() as db:
        _, lead = _make_workspace_and_lead(db)
        executor = ResearchToolExecutor(db, workspace_id=lead.workspace_id, lead=lead)

        result = executor.execute("compare_evidence", {})

        assert result["lead_id"] == lead.public_id
        assert "evidence_confidence" in result
        assert "research_coverage" in result
