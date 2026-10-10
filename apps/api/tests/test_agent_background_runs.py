from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from test_workspace_e2e import _build_session_factory, _login, _override_client, _seed_workspace

from app.core.config import clear_settings_cache
from app.modules.agents import events
from app.modules.agents.models import AgentEvent, AgentRun
from app.modules.agents.runtime import AgentRuntime
from app.modules.leads.models import Lead
from app.modules.users.models import User


def _use_stub_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("TAVILY_RUNTIME_MODE", "demo")
    monkeypatch.setenv("APIFY_RUNTIME_MODE", "demo")
    clear_settings_cache()


def _prepare(session_factory: sessionmaker[Session], admin_email: str) -> tuple[AgentRun, int]:
    with session_factory() as db:
        user = db.scalar(select(User).where(User.email == admin_email))
        assert user is not None
        lead = db.scalar(select(Lead).where(Lead.workspace_id == user.workspace_id))
        run = AgentRuntime().prepare_start(
            db,
            workspace_id=user.workspace_id,
            lead=lead,
            current_user=user,
            goal="Research this lead.",
        )
        return run, user.id


def _event_types(session_factory: sessionmaker[Session], run_id: int) -> list[str]:
    with session_factory() as db:
        return list(
            db.scalars(
                select(AgentEvent.event_type)
                .where(AgentEvent.agent_run_id == run_id)
                .order_by(AgentEvent.seq)
            )
        )


def test_create_returns_before_the_model_is_called(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_stub_runtime(monkeypatch)
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    seen: list[str] = []

    def record_only(self: AgentRuntime, *_: Any, run_id: int, **__: Any) -> None:
        seen.append(_event_types(session_factory, run_id)[-1])

    monkeypatch.setattr(AgentRuntime, "continue_in_background", record_only)
    with _override_client(session_factory) as client:
        headers = {"Authorization": f"Bearer {_login(client, seed)}"}
        response = client.post(
            "/api/v1/agent/runs",
            json={"goal": "Research this lead.", "lead_id": seed.lead_public_id},
            headers=headers,
        )

    assert response.status_code == 201
    assert response.json()["status"] == "running"
    # The loop is handed a committed run that has not reached the model yet.
    assert seen == [events.AGENT_STARTED]


def test_background_loop_drives_the_run_to_its_first_pause(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_stub_runtime(monkeypatch)
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    run, user_id = _prepare(session_factory, seed.admin_email)

    AgentRuntime().continue_in_background(
        session_factory, workspace_id=run.workspace_id, run_id=run.id, user_id=user_id
    )

    with session_factory() as db:
        assert db.get(AgentRun, run.id).status == "waiting_for_approval"  # type: ignore[union-attr]
    assert events.MODEL_STARTED in _event_types(session_factory, run.id)


def test_a_cancel_from_another_request_stops_the_background_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_stub_runtime(monkeypatch)
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    run, user_id = _prepare(session_factory, seed.admin_email)
    with session_factory() as db:
        AgentRuntime().cancel(db, workspace_id=run.workspace_id, run_id=run.public_id)

    # A run cancelled before the task picks it up is left alone.
    AgentRuntime().continue_in_background(
        session_factory, workspace_id=run.workspace_id, run_id=run.id, user_id=user_id
    )
    assert events.MODEL_STARTED not in _event_types(session_factory, run.id)

    # And one cancelled mid-loop stops at the next step boundary.
    run, user_id = _prepare(session_factory, seed.admin_email)
    runtime = AgentRuntime()
    original = runtime._handle_tool_call

    def cancel_after_first_tool(*args: Any, **kwargs: Any) -> str:
        outcome = original(*args, **kwargs)
        with session_factory() as other:
            runtime.cancel(other, workspace_id=run.workspace_id, run_id=run.public_id)
        return outcome

    monkeypatch.setattr(runtime, "_handle_tool_call", cancel_after_first_tool)
    runtime.continue_in_background(
        session_factory, workspace_id=run.workspace_id, run_id=run.id, user_id=user_id
    )

    with session_factory() as db:
        assert db.get(AgentRun, run.id).status == "cancelled"  # type: ignore[union-attr]
    assert _event_types(session_factory, run.id).count(events.MODEL_STARTED) == 1


def test_an_unexpected_error_fails_the_run_instead_of_leaving_it_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_stub_runtime(monkeypatch)
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    run, user_id = _prepare(session_factory, seed.admin_email)

    def explode(*_: Any, **__: Any) -> AgentRun:
        raise RuntimeError("boom")

    runtime = AgentRuntime()
    monkeypatch.setattr(runtime, "_loop", explode)
    runtime.continue_in_background(
        session_factory, workspace_id=run.workspace_id, run_id=run.id, user_id=user_id
    )

    with session_factory() as db:
        stored = db.get(AgentRun, run.id)
        assert stored is not None
        assert stored.status == "failed"
        assert stored.error_code == "agent_runtime_error"
        # Internal exception text never reaches the client.
        assert "boom" not in (stored.error_message or "")
    assert _event_types(session_factory, run.id)[-1] == events.AGENT_FAILED
