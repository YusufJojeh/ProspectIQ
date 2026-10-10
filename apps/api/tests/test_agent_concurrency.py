from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from test_agent_runtime import _make_workspace_lead_user, _use_stub_runtime

from app.core.database import Base
from app.core.errors import ApiError, ConflictError
from app.modules.agents.action_gate import AgentActionGate
from app.modules.agents.models import AgentAction
from app.modules.agents.repository import AgentRepository
from app.modules.agents.runtime import AgentRuntime
from app.modules.leads.models import LeadNote


@pytest.fixture()
def session_factory(tmp_path: Any) -> sessionmaker[Session]:
    """A *file-backed* SQLite database, one connection per thread.

    The shared in-memory StaticPool used elsewhere in this suite hands every
    thread the same sqlite3 connection, which cannot be driven concurrently.
    These tests are specifically about two callers racing, so they need real
    separate connections contending for the same row -- that is what makes
    the conditional UPDATE in claim_action_for_decision meaningful here
    rather than trivially serialized by the test harness.
    """
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'concurrency.db'}",
        future=True,
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    return sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session
    )


def _start_run_with_pending_action(
    session_factory: sessionmaker[Session],
) -> tuple[int, int, str, int]:
    """Drive a stub run to its first pending AgentAction.

    Returns (workspace_id, lead_id, action_public_id, user_id).
    """
    with session_factory() as db:
        _, lead, user = _make_workspace_lead_user(db)
        run = AgentRuntime().start(
            db,
            workspace_id=lead.workspace_id,
            lead=lead,
            current_user=user,
            goal="Research this lead and propose next steps.",
        )
        pending = AgentRepository().list_pending_actions_for_run(db, run.id)
        assert len(pending) == 1
        return lead.workspace_id, lead.id, pending[0].public_id, user.id


def _count_notes(session_factory: sessionmaker[Session], lead_id: int) -> int:
    with session_factory() as db:
        return int(
            db.scalar(select(func.count(LeadNote.id)).where(LeadNote.lead_id == lead_id)) or 0
        )


def _action_status(session_factory: sessionmaker[Session], action_id: str) -> str:
    with session_factory() as db:
        action = db.scalar(select(AgentAction).where(AgentAction.public_id == action_id))
        assert action is not None
        return action.status


# --- Two simultaneous approvals ----------------------------------------


def test_two_simultaneous_approvals_execute_the_mutation_exactly_once(monkeypatch, session_factory: sessionmaker[Session]) -> None:  # type: ignore[no-untyped-def]
    """The core concurrency guarantee: whichever caller's conditional UPDATE
    flips pending -> executing is the only one that reaches the domain
    service. The loser must not produce a second note."""
    _use_stub_runtime(monkeypatch)
    workspace_id, lead_id, action_id, user_id = _start_run_with_pending_action(session_factory)
    assert _count_notes(session_factory, lead_id) == 0

    barrier = threading.Barrier(4)
    outcomes: list[Any] = []
    lock = threading.Lock()

    def _approve() -> None:
        with session_factory() as db:
            user = _load_user(db, user_id)
            barrier.wait(timeout=10)
            try:
                action = AgentActionGate().approve(
                    db, workspace_id=workspace_id, action_id=action_id, current_user=user
                )
                result: Any = action.status
            except ConflictError as exc:
                result = f"conflict:{exc.detail}"
            with lock:
                outcomes.append(result)

    threads = [threading.Thread(target=_approve) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert len(outcomes) == 4
    assert _count_notes(session_factory, lead_id) == 1, "exactly one mutation must be applied"
    assert _action_status(session_factory, action_id) == "executed"


def _load_user(db: Session, user_id: int) -> Any:
    from app.modules.users.models import User

    user = db.scalar(select(User).where(User.id == user_id))
    assert user is not None
    return user


# --- Approve / reject race ---------------------------------------------


def test_approve_and_reject_race_resolves_to_one_terminal_state(monkeypatch, session_factory: sessionmaker[Session]) -> None:  # type: ignore[no-untyped-def]
    _use_stub_runtime(monkeypatch)
    workspace_id, lead_id, action_id, user_id = _start_run_with_pending_action(session_factory)

    barrier = threading.Barrier(2)
    errors: list[str] = []

    def _decide(reject: bool) -> None:
        with session_factory() as db:
            user = _load_user(db, user_id)
            gate = AgentActionGate()
            barrier.wait(timeout=10)
            try:
                if reject:
                    gate.reject(
                        db,
                        workspace_id=workspace_id,
                        action_id=action_id,
                        current_user=user,
                        reason="not now",
                    )
                else:
                    gate.approve(
                        db, workspace_id=workspace_id, action_id=action_id, current_user=user
                    )
            except ConflictError as exc:
                errors.append(exc.detail)

    threads = [
        threading.Thread(target=_decide, args=(False,)),
        threading.Thread(target=_decide, args=(True,)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    final = _action_status(session_factory, action_id)
    assert final in {"executed", "rejected"}, final
    notes = _count_notes(session_factory, lead_id)
    # If approve won, exactly one note exists; if reject won, none does.
    assert notes == (1 if final == "executed" else 0)


# --- HTTP retry / repeated approval ------------------------------------


def test_repeated_approval_after_success_is_idempotent(monkeypatch, session_factory: sessionmaker[Session]) -> None:  # type: ignore[no-untyped-def]
    """A client retrying an approve that already succeeded (lost response,
    double-click, proxy retry) gets the same executed action back and does
    not mutate anything a second time."""
    _use_stub_runtime(monkeypatch)
    workspace_id, lead_id, action_id, user_id = _start_run_with_pending_action(session_factory)

    with session_factory() as db:
        user = _load_user(db, user_id)
        gate = AgentActionGate()
        first = gate.approve(
            db, workspace_id=workspace_id, action_id=action_id, current_user=user
        )
        second = gate.approve(
            db, workspace_id=workspace_id, action_id=action_id, current_user=user
        )
        third = gate.approve(
            db, workspace_id=workspace_id, action_id=action_id, current_user=user
        )

    assert first.status == second.status == third.status == "executed"
    assert first.public_id == second.public_id == third.public_id
    assert _count_notes(session_factory, lead_id) == 1


def test_rejecting_an_executed_action_does_not_undo_it(monkeypatch, session_factory: sessionmaker[Session]) -> None:  # type: ignore[no-untyped-def]
    _use_stub_runtime(monkeypatch)
    workspace_id, lead_id, action_id, user_id = _start_run_with_pending_action(session_factory)

    with session_factory() as db:
        user = _load_user(db, user_id)
        gate = AgentActionGate()
        gate.approve(db, workspace_id=workspace_id, action_id=action_id, current_user=user)
        after = gate.reject(
            db,
            workspace_id=workspace_id,
            action_id=action_id,
            current_user=user,
            reason="changed my mind",
        )

    assert after.status == "executed"
    assert _count_notes(session_factory, lead_id) == 1


# --- Expiry boundary ----------------------------------------------------


def test_expired_action_cannot_be_approved_and_is_marked_expired(monkeypatch, session_factory: sessionmaker[Session]) -> None:  # type: ignore[no-untyped-def]
    _use_stub_runtime(monkeypatch)
    workspace_id, lead_id, action_id, user_id = _start_run_with_pending_action(session_factory)

    with session_factory() as db:
        action = db.scalar(select(AgentAction).where(AgentAction.public_id == action_id))
        assert action is not None
        action.expires_at = datetime.now(tz=UTC).replace(tzinfo=None) - timedelta(seconds=1)
        db.add(action)
        db.commit()

        user = _load_user(db, user_id)
        with pytest.raises(ConflictError):
            AgentActionGate().approve(
                db, workspace_id=workspace_id, action_id=action_id, current_user=user
            )

    assert _action_status(session_factory, action_id) == "expired"
    assert _count_notes(session_factory, lead_id) == 0


def test_action_still_valid_one_second_before_expiry_executes(monkeypatch, session_factory: sessionmaker[Session]) -> None:  # type: ignore[no-untyped-def]
    """The boundary is checked, not merely approximated."""
    _use_stub_runtime(monkeypatch)
    workspace_id, lead_id, action_id, user_id = _start_run_with_pending_action(session_factory)

    with session_factory() as db:
        action = db.scalar(select(AgentAction).where(AgentAction.public_id == action_id))
        assert action is not None
        action.expires_at = datetime.now(tz=UTC).replace(tzinfo=None) + timedelta(seconds=30)
        db.add(action)
        db.commit()
        user = _load_user(db, user_id)
        approved = AgentActionGate().approve(
            db, workspace_id=workspace_id, action_id=action_id, current_user=user
        )

    assert approved.status == "executed"
    assert _count_notes(session_factory, lead_id) == 1


# --- Executor failure ---------------------------------------------------


def test_domain_execution_failure_marks_action_failed_without_mutating(monkeypatch, session_factory: sessionmaker[Session]) -> None:  # type: ignore[no-untyped-def]
    _use_stub_runtime(monkeypatch)
    workspace_id, lead_id, action_id, user_id = _start_run_with_pending_action(session_factory)

    def _boom(self: Any, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise ApiError("Downstream service unavailable.")

    monkeypatch.setattr(
        "app.modules.agents.action_gate.AgentToolExecutor.execute_action", _boom
    )

    with session_factory() as db:
        user = _load_user(db, user_id)
        failed = AgentActionGate().approve(
            db, workspace_id=workspace_id, action_id=action_id, current_user=user
        )

    assert failed.status == "failed"
    assert failed.failure_code == "execution_failed"
    assert _count_notes(session_factory, lead_id) == 0


def test_unhandled_executor_error_is_contained_as_a_failed_action(monkeypatch, session_factory: sessionmaker[Session]) -> None:  # type: ignore[no-untyped-def]
    _use_stub_runtime(monkeypatch)
    workspace_id, lead_id, action_id, user_id = _start_run_with_pending_action(session_factory)

    def _boom(self: Any, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("unexpected")

    monkeypatch.setattr(
        "app.modules.agents.action_gate.AgentToolExecutor.execute_action", _boom
    )

    with session_factory() as db:
        user = _load_user(db, user_id)
        failed = AgentActionGate().approve(
            db, workspace_id=workspace_id, action_id=action_id, current_user=user
        )

    assert failed.status == "failed"
    assert failed.failure_code == "internal_error"
    assert _count_notes(session_factory, lead_id) == 0


# --- Already-executing / non-pending states -----------------------------


def test_action_already_executing_cannot_be_claimed_again(monkeypatch, session_factory: sessionmaker[Session]) -> None:  # type: ignore[no-untyped-def]
    _use_stub_runtime(monkeypatch)
    workspace_id, lead_id, action_id, user_id = _start_run_with_pending_action(session_factory)

    with session_factory() as db:
        action = db.scalar(select(AgentAction).where(AgentAction.public_id == action_id))
        assert action is not None
        action.status = "executing"
        db.add(action)
        db.commit()

        user = _load_user(db, user_id)
        with pytest.raises(ConflictError):
            AgentActionGate().approve(
                db, workspace_id=workspace_id, action_id=action_id, current_user=user
            )
        with pytest.raises(ConflictError):
            AgentActionGate().reject(
                db,
                workspace_id=workspace_id,
                action_id=action_id,
                current_user=user,
                reason=None,
            )

    assert _count_notes(session_factory, lead_id) == 0


def test_payload_tampered_after_proposal_fails_integrity_check(monkeypatch, session_factory: sessionmaker[Session]) -> None:  # type: ignore[no-untyped-def]
    """The approved payload must equal the executed payload. If the stored
    payload no longer hashes to payload_hash, nothing is executed."""
    _use_stub_runtime(monkeypatch)
    workspace_id, lead_id, action_id, user_id = _start_run_with_pending_action(session_factory)

    with session_factory() as db:
        action = db.scalar(select(AgentAction).where(AgentAction.public_id == action_id))
        assert action is not None
        tampered = dict(action.payload_json)
        tampered["note"] = "A different note nobody approved."
        action.payload_json = tampered
        db.add(action)
        db.commit()

        user = _load_user(db, user_id)
        with pytest.raises(ConflictError):
            AgentActionGate().approve(
                db, workspace_id=workspace_id, action_id=action_id, current_user=user
            )

    assert _count_notes(session_factory, lead_id) == 0
    assert _action_status(session_factory, action_id) == "pending"
