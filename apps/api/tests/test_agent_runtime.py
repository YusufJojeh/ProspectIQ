from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import clear_settings_cache
from app.core.database import Base
from app.modules.agents.models import AgentAction  # noqa: F401
from app.modules.agents.repository import AgentRepository
from app.modules.agents.runtime import AgentRuntime, AgentTurn, ToolCallRequest
from app.modules.leads.models import Lead
from app.modules.provider_serpapi.models import ProviderFetch  # noqa: F401
from app.modules.research.models import ResearchContradiction  # noqa: F401
from app.modules.search_jobs.models import SearchJob  # noqa: F401
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
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session
    )


def _use_stub_runtime(monkeypatch: Any) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("TAVILY_RUNTIME_MODE", "demo")
    monkeypatch.setenv("APIFY_RUNTIME_MODE", "demo")
    clear_settings_cache()


def _make_workspace_lead_user(db: Session) -> tuple[Workspace, Lead, User]:
    workspace = Workspace(name="LeadScope Workspace")
    db.add(workspace)
    db.commit()
    db.refresh(workspace)

    role = Role(key="admin", label="Admin")
    db.add(role)
    db.commit()
    db.refresh(role)

    lead = Lead(workspace_id=workspace.id, company_name="Acme Dental", website_url=None)
    db.add(lead)
    db.commit()
    db.refresh(lead)

    user = User(
        workspace_id=workspace.id,
        role="admin",
        email="owner@example.com",
        hashed_password="x",
        full_name="Owner",
        status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return workspace, lead, user


def test_agent_run_blocked_runtime_fails_fast(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("JWT_SECRET", "x" * 40)
    monkeypatch.setenv("WEB_ORIGINS", "https://example.com")
    monkeypatch.setenv("DEFAULT_ADMIN_PASSWORD", "strong-password-1234")
    clear_settings_cache()
    try:
        session_factory = _build_session_factory()
        with session_factory() as db:
            _, lead, user = _make_workspace_lead_user(db)
            run = AgentRuntime().start(
                db, workspace_id=lead.workspace_id, lead=lead, current_user=user, goal="Research this lead."
            )
            assert run.status == "failed"
            assert run.error_code == "agent_runtime_blocked"
    finally:
        clear_settings_cache()


def test_agent_run_stub_pauses_for_approval_then_resumes_to_completion(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _use_stub_runtime(monkeypatch)
    session_factory = _build_session_factory()
    with session_factory() as db:
        _, lead, user = _make_workspace_lead_user(db)
        runtime = AgentRuntime()
        run = runtime.start(
            db, workspace_id=lead.workspace_id, lead=lead, current_user=user,
            goal="Research this lead deeply and propose next steps.",
        )

        assert run.status == "waiting_for_approval"
        assert run.write_proposal_count >= 1

        repository = AgentRepository()
        pending = repository.list_pending_actions_for_run(db, run.id)
        assert len(pending) == 1
        first_action = pending[0]
        assert first_action.tool_name == "add_lead_note"
        assert first_action.status == "pending"

        from app.modules.agents.action_gate import AgentActionGate

        gate = AgentActionGate()
        approved = gate.approve(
            db, workspace_id=lead.workspace_id, action_id=first_action.public_id, current_user=user
        )
        assert approved.status == "executed"
        assert approved.result_json is not None

        resumed = runtime.resume_after_action(
            db, workspace_id=lead.workspace_id, run_id=run.id, current_user=user
        )
        assert resumed is not None
        assert resumed.status == "waiting_for_approval"

        pending_2 = repository.list_pending_actions_for_run(db, run.id)
        assert len(pending_2) == 1
        second_action = pending_2[0]
        assert second_action.tool_name == "create_follow_up"

        approved_2 = gate.approve(
            db, workspace_id=lead.workspace_id, action_id=second_action.public_id, current_user=user
        )
        assert approved_2.status == "executed"

        finished = runtime.resume_after_action(
            db, workspace_id=lead.workspace_id, run_id=run.id, current_user=user
        )
        assert finished is not None
        assert finished.status == "completed"
        assert finished.final_answer_json is not None
        assert "answer" in finished.final_answer_json


def test_agent_action_reject_causes_no_mutation_and_run_still_resumes(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _use_stub_runtime(monkeypatch)
    session_factory = _build_session_factory()
    with session_factory() as db:
        _, lead, user = _make_workspace_lead_user(db)
        runtime = AgentRuntime()
        run = runtime.start(
            db, workspace_id=lead.workspace_id, lead=lead, current_user=user, goal="Research this lead."
        )
        repository = AgentRepository()
        pending = repository.list_pending_actions_for_run(db, run.id)
        action = pending[0]
        assert action.tool_name == "add_lead_note"

        from app.modules.agents.action_gate import AgentActionGate
        from app.modules.leads.models import LeadNote

        gate = AgentActionGate()
        rejected = gate.reject(
            db, workspace_id=lead.workspace_id, action_id=action.public_id,
            current_user=user, reason="Not needed.",
        )
        assert rejected.status == "rejected"
        notes = db.query(LeadNote).filter(LeadNote.lead_id == lead.id).all()
        assert notes == []

        resumed = runtime.resume_after_action(
            db, workspace_id=lead.workspace_id, run_id=run.id, current_user=user
        )
        assert resumed is not None
        assert resumed.status == "waiting_for_approval"


def test_agent_action_approve_is_idempotent_on_repeated_call(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _use_stub_runtime(monkeypatch)
    session_factory = _build_session_factory()
    with session_factory() as db:
        _, lead, user = _make_workspace_lead_user(db)
        runtime = AgentRuntime()
        run = runtime.start(
            db, workspace_id=lead.workspace_id, lead=lead, current_user=user, goal="Research this lead."
        )
        repository = AgentRepository()
        action = repository.list_pending_actions_for_run(db, run.id)[0]

        from app.modules.agents.action_gate import AgentActionGate
        from app.modules.leads.models import LeadNote

        gate = AgentActionGate()
        first = gate.approve(
            db, workspace_id=lead.workspace_id, action_id=action.public_id, current_user=user
        )
        second = gate.approve(
            db, workspace_id=lead.workspace_id, action_id=action.public_id, current_user=user
        )
        assert first.status == "executed"
        assert second.status == "executed"
        assert first.result_json == second.result_json
        notes = db.query(LeadNote).filter(LeadNote.lead_id == lead.id).all()
        assert len(notes) == 1


class _RepeatingCaller:
    def __init__(self) -> None:
        self._calls = 0

    def step(self, messages: list[dict[str, Any]], tool_defs: list[dict[str, Any]]) -> AgentTurn:
        self._calls += 1
        if self._calls <= 2:
            return AgentTurn(
                tool_call=ToolCallRequest(
                    id=f"c{self._calls}", name="get_lead_context", arguments={}
                ),
                final_content=None,
            )
        return AgentTurn(
            tool_call=None,
            final_content='{"answer": "done", "confidence": 0.5, "research_coverage": 0.5}',
        )


def test_agent_runtime_blocks_duplicate_tool_call_with_identical_arguments(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _use_stub_runtime(monkeypatch)
    monkeypatch.setattr(
        "app.modules.agents.runtime._StubAgentCaller", lambda initial_index=0: _RepeatingCaller()
    )
    session_factory = _build_session_factory()
    with session_factory() as db:
        _, lead, user = _make_workspace_lead_user(db)
        runtime = AgentRuntime()
        run = runtime.start(
            db, workspace_id=lead.workspace_id, lead=lead, current_user=user, goal="test"
        )
        assert run.status == "completed"

        tool_calls = runtime.repository.list_tool_calls(db, run.id)
        statuses = [tc.status for tc in tool_calls if tc.tool_name == "get_lead_context"]
        assert statuses == ["ok", "duplicate"]
