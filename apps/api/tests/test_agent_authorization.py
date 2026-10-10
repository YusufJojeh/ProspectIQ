from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker
from test_agent_runtime import (
    _build_session_factory,
    _make_workspace_lead_user,
    _use_stub_runtime,
)

from app.core.errors import ConflictError, NotFoundError
from app.modules.agents.action_gate import AgentActionGate
from app.modules.agents.models import AgentAction
from app.modules.agents.repository import AgentRepository
from app.modules.agents.runtime import AgentRuntime
from app.modules.leads.models import Lead, LeadNote
from app.modules.users.models import User, Workspace

# The authorization matrix. Each test below pins one row of it: who may see
# or decide what, checked at *decision* time rather than at proposal time,
# because the proposing run's context can be stale by the time a human
# clicks Approve.


def _seed(db: Session) -> tuple[Workspace, Lead, User]:
    return _make_workspace_lead_user(db)


def _second_workspace(db: Session) -> tuple[Workspace, User]:
    workspace = Workspace(name="Other Workspace")
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    user = User(
        workspace_id=workspace.id,
        role="admin",
        email="outsider@example.com",
        hashed_password="x",
        full_name="Outsider",
        status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return workspace, user


def _run_to_pending(db: Session, lead: Lead, user: User) -> tuple[Any, AgentAction]:
    run = AgentRuntime().start(
        db,
        workspace_id=lead.workspace_id,
        lead=lead,
        current_user=user,
        goal="Research this lead and propose next steps.",
    )
    pending = AgentRepository().list_pending_actions_for_run(db, run.id)
    assert pending
    return run, pending[0]


def test_foreign_workspace_cannot_read_a_run(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _use_stub_runtime(monkeypatch)
    session_factory: sessionmaker[Session] = _build_session_factory()
    with session_factory() as db:
        _, lead, user = _seed(db)
        run, _ = _run_to_pending(db, lead, user)
        other_workspace, _ = _second_workspace(db)

        repository = AgentRepository()
        assert (
            repository.get_run_by_public_id(
                db, workspace_id=other_workspace.id, run_id=run.public_id
            )
            is None
        )
        assert (
            repository.get_run_by_public_id(
                db, workspace_id=lead.workspace_id, run_id=run.public_id
            )
            is not None
        )


def test_foreign_workspace_cannot_read_or_decide_an_action(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _use_stub_runtime(monkeypatch)
    session_factory: sessionmaker[Session] = _build_session_factory()
    with session_factory() as db:
        _, lead, user = _seed(db)
        _, action = _run_to_pending(db, lead, user)
        other_workspace, outsider = _second_workspace(db)

        assert (
            AgentRepository().get_action_by_public_id(
                db, workspace_id=other_workspace.id, action_id=action.public_id
            )
            is None
        )
        with pytest.raises(NotFoundError):
            AgentActionGate().approve(
                db,
                workspace_id=other_workspace.id,
                action_id=action.public_id,
                current_user=outsider,
            )
        with pytest.raises(NotFoundError):
            AgentActionGate().reject(
                db,
                workspace_id=other_workspace.id,
                action_id=action.public_id,
                current_user=outsider,
                reason=None,
            )
        assert db.scalar(select(LeadNote).where(LeadNote.lead_id == lead.id)) is None


def test_confirming_user_must_belong_to_the_actions_workspace(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Even with the correct workspace_id in hand, a user whose own
    membership is elsewhere cannot approve: the gate re-checks the acting
    user's workspace at decision time."""
    _use_stub_runtime(monkeypatch)
    session_factory: sessionmaker[Session] = _build_session_factory()
    with session_factory() as db:
        _, lead, user = _seed(db)
        _, action = _run_to_pending(db, lead, user)
        _, outsider = _second_workspace(db)

        with pytest.raises(ConflictError):
            AgentActionGate().approve(
                db,
                workspace_id=lead.workspace_id,
                action_id=action.public_id,
                current_user=outsider,
            )
        assert db.scalar(select(LeadNote).where(LeadNote.lead_id == lead.id)) is None


def test_a_different_authorized_member_of_the_same_workspace_may_approve(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Approval is a workspace-level authority, not a per-user one: the
    colleague who reviews the proposal need not be whoever started the run."""
    _use_stub_runtime(monkeypatch)
    session_factory: sessionmaker[Session] = _build_session_factory()
    with session_factory() as db:
        workspace, lead, user = _seed(db)
        _, action = _run_to_pending(db, lead, user)

        colleague = User(
            workspace_id=workspace.id,
            role="agency_manager",
            email="colleague@example.com",
            hashed_password="x",
            full_name="Colleague",
            status="active",
        )
        db.add(colleague)
        db.commit()
        db.refresh(colleague)

        approved = AgentActionGate().approve(
            db,
            workspace_id=workspace.id,
            action_id=action.public_id,
            current_user=colleague,
        )
        assert approved.status == "executed"
        assert approved.approved_by_user_id == colleague.id


def test_deleted_lead_blocks_execution_of_a_pending_action(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The resource is re-verified at approval time, so an action proposed
    against a lead that has since been deleted cannot execute."""
    _use_stub_runtime(monkeypatch)
    session_factory: sessionmaker[Session] = _build_session_factory()
    with session_factory() as db:
        workspace, lead, user = _seed(db)
        _, action = _run_to_pending(db, lead, user)

        db.execute(delete(LeadNote).where(LeadNote.lead_id == lead.id))
        db.execute(delete(Lead).where(Lead.id == lead.id))
        db.commit()

        with pytest.raises(ConflictError):
            AgentActionGate().approve(
                db,
                workspace_id=workspace.id,
                action_id=action.public_id,
                current_user=user,
            )
        refreshed = db.scalar(
            select(AgentAction).where(AgentAction.public_id == action.public_id)
        )
        assert refreshed is not None
        assert refreshed.status == "pending"


def test_action_listing_is_scoped_to_the_callers_workspace(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _use_stub_runtime(monkeypatch)
    session_factory: sessionmaker[Session] = _build_session_factory()
    with session_factory() as db:
        workspace, lead, user = _seed(db)
        _run_to_pending(db, lead, user)
        other_workspace, _ = _second_workspace(db)

        repository = AgentRepository()
        mine, mine_total = repository.list_actions(
            db, workspace_id=workspace.id, status=None, page=1, per_page=50
        )
        theirs, theirs_total = repository.list_actions(
            db, workspace_id=other_workspace.id, status=None, page=1, per_page=50
        )
        assert mine_total >= 1 and mine
        assert theirs_total == 0 and theirs == []


def test_events_and_messages_carry_the_owning_workspace(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Every audit row is tenant-stamped, so a leak cannot be introduced by
    a later query that forgets to join through the run."""
    _use_stub_runtime(monkeypatch)
    session_factory: sessionmaker[Session] = _build_session_factory()
    with session_factory() as db:
        workspace, lead, user = _seed(db)
        run, _ = _run_to_pending(db, lead, user)

        repository = AgentRepository()
        events = repository.list_events(db, run.id)
        messages = repository.list_messages(db, run.id)
        tool_calls = repository.list_tool_calls(db, run.id)

        assert events and messages and tool_calls
        assert {event.workspace_id for event in events} == {workspace.id}
        assert {message.workspace_id for message in messages} == {workspace.id}
        assert {call.workspace_id for call in tool_calls} == {workspace.id}
