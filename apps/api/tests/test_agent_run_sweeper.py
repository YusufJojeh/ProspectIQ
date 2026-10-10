from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker
from test_workspace_e2e import _build_session_factory, _login, _override_client, _seed_workspace

from app.core.config import clear_settings_cache
from app.modules.agents import events
from app.modules.agents.models import AgentEvent, AgentRun
from app.modules.agents.runtime import AgentRuntime
from app.modules.users.models import User, Workspace


def _use_stub_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("TAVILY_RUNTIME_MODE", "demo")
    monkeypatch.setenv("APIFY_RUNTIME_MODE", "demo")
    clear_settings_cache()


def _admin(db: Session, email: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    assert user is not None
    return user


def _make_run(
    session_factory: sessionmaker[Session],
    *,
    workspace_id: int,
    user_id: int,
    status: str,
    idle_seconds: int,
) -> int:
    with session_factory() as db:
        run = AgentRun(
            workspace_id=workspace_id,
            created_by_user_id=user_id,
            goal="g",
            status=status,
        )
        db.add(run)
        db.commit()
        # Backdate after the insert: updated_at is refreshed on every write.
        db.execute(
            update(AgentRun)
            .where(AgentRun.id == run.id)
            .values(updated_at=datetime.now(tz=UTC) - timedelta(seconds=idle_seconds))
        )
        db.commit()
        return run.id


def _run(session_factory: sessionmaker[Session], run_id: int) -> AgentRun:
    with session_factory() as db:
        run = db.get(AgentRun, run_id)
        assert run is not None
        return run


def _event_types(session_factory: sessionmaker[Session], run_id: int) -> list[str]:
    with session_factory() as db:
        return list(
            db.scalars(
                select(AgentEvent.event_type)
                .where(AgentEvent.agent_run_id == run_id)
                .order_by(AgentEvent.seq)
            )
        )


def test_only_running_runs_idle_past_the_window_are_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_stub_runtime(monkeypatch)
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    with session_factory() as db:
        admin = _admin(db, seed.admin_email)
    ws, uid = admin.workspace_id, admin.id

    stale = _make_run(session_factory, workspace_id=ws, user_id=uid, status="running", idle_seconds=3600)
    fresh = _make_run(session_factory, workspace_id=ws, user_id=uid, status="running", idle_seconds=30)
    parked = _make_run(
        session_factory, workspace_id=ws, user_id=uid, status="waiting_for_approval", idle_seconds=3600
    )

    with session_factory() as db:
        assert AgentRuntime().sweep_abandoned_runs(db, workspace_id=ws) == 1

    swept = _run(session_factory, stale)
    assert swept.status == "failed"
    assert swept.error_code == "agent_run_abandoned"
    assert swept.completed_at is not None
    # The failure is an event too, so a stream still following the run closes.
    assert _event_types(session_factory, stale) == [events.AGENT_FAILED]
    assert _run(session_factory, fresh).status == "running"
    # A run parked for approval is waiting on a person, not on a lost loop.
    assert _run(session_factory, parked).status == "waiting_for_approval"

    # Sweeping again is a no-op.
    with session_factory() as db:
        assert AgentRuntime().sweep_abandoned_runs(db, workspace_id=ws) == 0
    assert _event_types(session_factory, stale) == [events.AGENT_FAILED]


def test_the_window_never_undercuts_the_runtime_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_stub_runtime(monkeypatch)
    monkeypatch.setenv("AGENT_STALE_RUN_SECONDS", "120")
    monkeypatch.setenv("AGENT_MAX_RUNTIME_SECONDS", "600")
    clear_settings_cache()
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    with session_factory() as db:
        admin = _admin(db, seed.admin_email)

    # Idle 10 minutes, but a live loop may legitimately run 600s + slack.
    slow = _make_run(
        session_factory, workspace_id=admin.workspace_id, user_id=admin.id, status="running", idle_seconds=600
    )
    with session_factory() as db:
        assert AgentRuntime().sweep_abandoned_runs(db) == 0
    assert _run(session_factory, slow).status == "running"


def test_a_workspace_sweep_leaves_other_workspaces_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_stub_runtime(monkeypatch)
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    with session_factory() as db:
        admin = _admin(db, seed.admin_email)
        other = Workspace(name="Other")
        db.add(other)
        db.commit()
        other_id = other.id

    mine = _make_run(
        session_factory, workspace_id=admin.workspace_id, user_id=admin.id, status="running", idle_seconds=3600
    )
    theirs = _make_run(
        session_factory, workspace_id=other_id, user_id=admin.id, status="running", idle_seconds=3600
    )
    with session_factory() as db:
        AgentRuntime().sweep_abandoned_runs(db, workspace_id=admin.workspace_id)

    assert _run(session_factory, mine).status == "failed"
    assert _run(session_factory, theirs).status == "running"


def test_reading_a_run_through_the_api_sweeps_it(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_stub_runtime(monkeypatch)
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    with session_factory() as db:
        admin = _admin(db, seed.admin_email)
    stale = _make_run(
        session_factory, workspace_id=admin.workspace_id, user_id=admin.id, status="running", idle_seconds=3600
    )
    public_id = _run(session_factory, stale).public_id

    with _override_client(session_factory) as client:
        headers = {"Authorization": f"Bearer {_login(client, seed)}"}
        body = client.get(f"/api/v1/agent/runs/{public_id}", headers=headers).json()
        stream = client.get(f"/api/v1/agent/runs/{public_id}/stream", headers=headers)

    assert body["status"] == "failed"
    assert body["error_code"] == "agent_run_abandoned"
    # The stream treats the swept run as closed and replays its failure.
    assert "event: agent_failed" in stream.text


def test_a_loop_that_was_swept_stops_instead_of_overwriting_the_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_stub_runtime(monkeypatch)
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    with session_factory() as db:
        admin = _admin(db, seed.admin_email)
        run = AgentRuntime().prepare_start(
            db, workspace_id=admin.workspace_id, lead=None, current_user=admin, goal="g"
        )

    runtime = AgentRuntime()
    original = runtime._handle_tool_call

    def swept_after_first_tool(*args: Any, **kwargs: Any) -> str:
        outcome = original(*args, **kwargs)
        with session_factory() as other:
            other.execute(
                update(AgentRun)
                .where(AgentRun.id == run.id)
                .values(status="failed", error_code="agent_run_abandoned")
            )
            other.commit()
        return outcome

    monkeypatch.setattr(runtime, "_handle_tool_call", swept_after_first_tool)
    runtime.continue_in_background(
        session_factory, workspace_id=run.workspace_id, run_id=run.id, user_id=admin.id
    )

    stored = _run(session_factory, run.id)
    assert stored.status == "failed"
    assert stored.error_code == "agent_run_abandoned"
    assert _event_types(session_factory, run.id).count(events.MODEL_STARTED) == 1

