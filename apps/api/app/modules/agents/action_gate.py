from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import ApiError, ConflictError, NotFoundError
from app.modules.agents import events
from app.modules.agents.models import AgentAction, AgentRun
from app.modules.agents.repository import AgentRepository
from app.modules.agents.tool_executor import AgentToolExecutor
from app.modules.leads.repository import LeadsRepository
from app.modules.users.models import User

logger = logging.getLogger(__name__)


def hash_payload(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _utcnow() -> datetime:
    """Naive UTC 'now', matching how DateTime() columns round-trip through
    SQLAlchemy/SQLite in this codebase (tzinfo is stripped on persist, so a
    freshly-loaded ORM datetime is always naive)."""
    return datetime.now(tz=UTC).replace(tzinfo=None)


class AgentActionGate:
    """The single place a pending AgentAction can become a real domain
    mutation. Every step here re-verifies state at decision time rather than
    trusting anything captured when the action was proposed: the proposing
    run's permission context may be stale by the time a human clicks
    Approve, and the resource itself may have been deleted or moved in the
    meantime.

    Concurrency safety comes entirely from
    AgentRepository.claim_action_for_decision's single conditional UPDATE:
    whichever caller's UPDATE actually flips status='pending' -> 'executing'
    is the only one that proceeds to call the domain service. A second,
    concurrent approve (or a double-click) sees rowcount=0 and is treated as
    a no-op against the now-already-decided action, never as a second
    mutation.
    """

    def __init__(
        self,
        repository: AgentRepository | None = None,
        leads_repository: LeadsRepository | None = None,
    ) -> None:
        self.repository = repository or AgentRepository()
        self.leads_repository = leads_repository or LeadsRepository()

    def _emit(
        self,
        db: Session,
        run: AgentRun,
        action: AgentAction,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Record one approval-lifecycle event against the proposing run.

        These are the events a live SSE client needs to follow an approval
        through to its domain effect: action_approved -> action_executing ->
        action_completed/action_failed. They carry identifiers and status
        only, never the payload body (which the human already saw in the
        preview) and never any model reasoning.
        """
        self.repository.add_event(
            db,
            agent_run_id=run.id,
            workspace_id=run.workspace_id,
            run_public_id=run.public_id,
            event_type=event_type,
            payload={
                "action_id": action.public_id,
                "tool_name": action.tool_name,
                "risk_level": action.risk_level,
                **(payload or {}),
            },
        )

    def approve(
        self, db: Session, *, workspace_id: int, action_id: str, current_user: User
    ) -> AgentAction:
        action = self._get_or_raise(db, workspace_id=workspace_id, action_id=action_id)

        if action.status == "executed":
            return action  # repeated approval after success is idempotent
        if action.status != "pending":
            raise ConflictError(f"Action is '{action.status}' and cannot be approved.")
        if action.expires_at <= _utcnow():
            self.repository.claim_action_for_decision(
                db, workspace_id=workspace_id, action_id=action.id, new_status="expired"
            )
            raise ConflictError("Action has expired and can no longer be approved.")
        if current_user.workspace_id != workspace_id:
            raise ConflictError("Confirming user is not a member of this workspace.")
        if hash_payload(action.payload_json) != action.payload_hash:
            raise ConflictError("Action payload failed integrity verification.")

        run = self.repository.get_run_by_id(db, workspace_id=workspace_id, run_id=action.agent_run_id)
        if run is None:
            raise NotFoundError("The agent run for this action was not found.")
        lead = (
            self.leads_repository.get_by_id_for_workspace(
                db, workspace_id=workspace_id, lead_id=run.lead_id
            )
            if run.lead_id is not None
            else None
        )
        if run.lead_id is not None and lead is None:
            raise ConflictError("The lead this action targets no longer exists.")

        claimed = self.repository.claim_action_for_decision(
            db, workspace_id=workspace_id, action_id=action.id, new_status="executing"
        )
        if not claimed:
            refreshed = self._get_or_raise(db, workspace_id=workspace_id, action_id=action_id)
            if refreshed.status == "executed":
                return refreshed
            raise ConflictError(
                f"Action could not be claimed for approval (current status: {refreshed.status})."
            )

        db.refresh(action)
        self._emit(db, run, action, events.ACTION_APPROVED, {"approved_by": current_user.public_id})
        self._emit(db, run, action, events.ACTION_EXECUTING)
        try:
            executor = AgentToolExecutor(
                db, workspace_id=workspace_id, lead=lead, current_user=current_user
            )
            result = executor.execute_action(action.tool_name, action.payload_json)
        except ApiError as exc:
            self._emit(
                db, run, action, events.ACTION_FAILED, {"failure_code": "execution_failed"}
            )
            return self.repository.finalize_action(
                db,
                action,
                status="failed",
                failure_code="execution_failed",
                failure_message=exc.detail,
                approved_by_user_id=current_user.id,
                approved_at=_utcnow(),
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("agent_action.execution_unhandled_error action_id=%s", action.public_id)
            self._emit(db, run, action, events.ACTION_FAILED, {"failure_code": "internal_error"})
            return self.repository.finalize_action(
                db,
                action,
                status="failed",
                failure_code="internal_error",
                failure_message=str(exc),
                approved_by_user_id=current_user.id,
                approved_at=_utcnow(),
            )

        executed = self.repository.finalize_action(
            db,
            action,
            status="executed",
            result=result,
            approved_by_user_id=current_user.id,
            approved_at=_utcnow(),
            executed_at=_utcnow(),
        )
        self._emit(db, run, executed, events.ACTION_COMPLETED)
        return executed

    def reject(
        self,
        db: Session,
        *,
        workspace_id: int,
        action_id: str,
        current_user: User,
        reason: str | None,
    ) -> AgentAction:
        action = self._get_or_raise(db, workspace_id=workspace_id, action_id=action_id)
        if action.status in {"rejected", "executed"}:
            return action
        if action.status != "pending":
            raise ConflictError(f"Action is '{action.status}' and cannot be rejected.")

        claimed = self.repository.claim_action_for_decision(
            db, workspace_id=workspace_id, action_id=action.id, new_status="rejected"
        )
        if not claimed:
            return self._get_or_raise(db, workspace_id=workspace_id, action_id=action_id)

        db.refresh(action)
        rejected = self.repository.finalize_action(
            db,
            action,
            status="rejected",
            failure_code="rejected_by_user",
            failure_message=reason,
            approved_by_user_id=current_user.id,
            approved_at=_utcnow(),
        )
        run = self.repository.get_run_by_id(
            db, workspace_id=workspace_id, run_id=action.agent_run_id
        )
        if run is not None:
            self._emit(
                db, run, rejected, events.ACTION_REJECTED, {"rejected_by": current_user.public_id}
            )
        return rejected

    def _get_or_raise(self, db: Session, *, workspace_id: int, action_id: str) -> AgentAction:
        action = self.repository.get_action_by_public_id(
            db, workspace_id=workspace_id, action_id=action_id
        )
        if action is None:
            raise NotFoundError("Agent action was not found.")
        return action


__all__ = ["AgentActionGate", "hash_payload"]
