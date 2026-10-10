from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import clear_settings_cache
from app.core.database import Base
from app.modules.leads.models import Lead
from app.modules.provider_serpapi.models import ProviderFetch  # noqa: F401
from app.modules.research.agent_loop import ResearchAgentLoop
from app.modules.research.models import ResearchContradiction  # noqa: F401
from app.modules.search_jobs.models import SearchJob  # noqa: F401
from app.modules.users.models import Workspace
from app.shared.enums.jobs import ProviderFetchStatus


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


def _make_workspace_and_lead(db: Session) -> Lead:
    workspace = Workspace(name="LeadScope Workspace")
    db.add(workspace)
    db.commit()
    db.refresh(workspace)

    lead = Lead(workspace_id=workspace.id, company_name="Acme Dental", website_url=None)
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def test_agent_loop_blocked_runtime_returns_error_without_calling_openai(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("JWT_SECRET", "x" * 40)
    monkeypatch.setenv("WEB_ORIGINS", "https://example.com")
    monkeypatch.setenv("DEFAULT_ADMIN_PASSWORD", "strong-password-1234")
    clear_settings_cache()
    try:
        session_factory = _build_session_factory()
        with session_factory() as db:
            lead = _make_workspace_and_lead(db)

            result = ResearchAgentLoop().run(
                db, workspace_id=lead.workspace_id, lead=lead, depth="quick"
            )

            assert result.status == ProviderFetchStatus.ERROR.value
            assert result.mode == "agentic"
            assert result.last_provider_fetch_public_id is None
            assert "OPENAI_API_KEY" in result.message
    finally:
        clear_settings_cache()


def test_agent_loop_stub_runtime_runs_scripted_tool_sequence_and_persists_result() -> None:
    monkeypatch_env = {
        "APP_ENV": "test",
        "TAVILY_RUNTIME_MODE": "demo",
        "APIFY_RUNTIME_MODE": "demo",
    }
    import os

    previous = {key: os.environ.get(key) for key in monkeypatch_env}
    os.environ.update(monkeypatch_env)
    clear_settings_cache()
    try:
        session_factory = _build_session_factory()
        with session_factory() as db:
            lead = _make_workspace_and_lead(db)

            result = ResearchAgentLoop().run(
                db, workspace_id=lead.workspace_id, lead=lead, depth="standard"
            )

            assert result.mode == "agentic"
            assert result.tool_calls_made == 4
            assert result.status == ProviderFetchStatus.OK.value
            assert "tavily" in result.providers_used
            assert result.last_provider_fetch_public_id is not None
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        clear_settings_cache()
