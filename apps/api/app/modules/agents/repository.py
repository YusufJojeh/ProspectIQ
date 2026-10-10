from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.modules.agents.events import (
    LiveAgentEvent,
    get_event_broker,
    sanitize_payload,
)
from app.modules.agents.models import (
    AgentAction,
    AgentEvent,
    AgentMessage,
    AgentRun,
    AgentToolCall,
)

logger = logging.getLogger(__name__)


class AgentRepository:
    """Persistence for the agent runtime.

    `claim_action_for_decision` is the one method that matters for
    correctness under concurrency: it performs a single conditional
    ``UPDATE ... WHERE status = 'pending'`` and inspects `rowcount` to decide
    whether *this* caller won the race, so two simultaneous approve/reject
    requests (or a double-click) can transition an AgentAction at most once.
    """

    def create_run(
        self,
        db: Session,
        *,
        workspace_id: int,
        lead_id: int | None,
        created_by_user_id: int,
        goal: str,
        provider: str,
        model: str,
    ) -> AgentRun:
        run = AgentRun(
            workspace_id=workspace_id,
            lead_id=lead_id,
            created_by_user_id=created_by_user_id,
            goal=goal,
            provider=provider,
            model=model,
            status="queued",
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    def get_run_by_public_id(
        self, db: Session, *, workspace_id: int, run_id: str
    ) -> AgentRun | None:
        statement = select(AgentRun).where(
            AgentRun.workspace_id == workspace_id, AgentRun.public_id == run_id
        )
        return db.scalar(statement)

    def get_run_by_id(self, db: Session, *, workspace_id: int, run_id: int) -> AgentRun | None:
        statement = select(AgentRun).where(
            AgentRun.workspace_id == workspace_id, AgentRun.id == run_id
        )
        return db.scalar(statement)

    def save_run(self, db: Session, run: AgentRun) -> AgentRun:
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    def next_message_seq(self, db: Session, agent_run_id: int) -> int:
        current = db.scalar(
            select(AgentMessage.seq)
            .where(AgentMessage.agent_run_id == agent_run_id)
            .order_by(AgentMessage.seq.desc())
            .limit(1)
        )
        return (current or 0) + 1

    def add_message(
        self,
        db: Session,
        *,
        agent_run_id: int,
        workspace_id: int,
        role: str,
        content: str | None,
        tool_name: str | None = None,
        tool_call_public_id: str | None = None,
    ) -> AgentMessage:
        message = AgentMessage(
            agent_run_id=agent_run_id,
            workspace_id=workspace_id,
            seq=self.next_message_seq(db, agent_run_id),
            role=role,
            content=content,
            tool_name=tool_name,
            tool_call_public_id=tool_call_public_id,
        )
        db.add(message)
        db.commit()
        db.refresh(message)
        return message

    def list_messages(self, db: Session, agent_run_id: int) -> list[AgentMessage]:
        statement = (
            select(AgentMessage)
            .where(AgentMessage.agent_run_id == agent_run_id)
            .order_by(AgentMessage.seq.asc())
        )
        return list(db.scalars(statement))

    def next_tool_call_seq(self, db: Session, agent_run_id: int) -> int:
        current = db.scalar(
            select(AgentToolCall.seq)
            .where(AgentToolCall.agent_run_id == agent_run_id)
            .order_by(AgentToolCall.seq.desc())
            .limit(1)
        )
        return (current or 0) + 1

    def add_tool_call(
        self,
        db: Session,
        *,
        agent_run_id: int,
        workspace_id: int,
        tool_name: str,
        tool_type: str,
        arguments: dict[str, Any],
        arguments_hash: str,
        status: str = "pending",
    ) -> AgentToolCall:
        tool_call = AgentToolCall(
            agent_run_id=agent_run_id,
            workspace_id=workspace_id,
            seq=self.next_tool_call_seq(db, agent_run_id),
            tool_name=tool_name,
            tool_type=tool_type,
            arguments_json=arguments,
            arguments_hash=arguments_hash,
            status=status,
        )
        db.add(tool_call)
        db.commit()
        db.refresh(tool_call)
        return tool_call

    def complete_tool_call(
        self,
        db: Session,
        tool_call: AgentToolCall,
        *,
        status: str,
        result: dict[str, Any] | None,
        duration_ms: int,
    ) -> AgentToolCall:
        tool_call.status = status
        tool_call.result_json = result
        tool_call.duration_ms = duration_ms
        db.add(tool_call)
        db.commit()
        db.refresh(tool_call)
        return tool_call

    def list_tool_calls(self, db: Session, agent_run_id: int) -> list[AgentToolCall]:
        statement = (
            select(AgentToolCall)
            .where(AgentToolCall.agent_run_id == agent_run_id)
            .order_by(AgentToolCall.seq.asc())
        )
        return list(db.scalars(statement))

    def add_event(
        self,
        db: Session,
        *,
        agent_run_id: int,
        workspace_id: int,
        event_type: str,
        payload: dict[str, Any] | None = None,
        run_public_id: str | None = None,
    ) -> AgentEvent:
        """Persist one lifecycle event, then publish it to live subscribers.

        The ordering is the contract: the AgentEvent row is committed
        *before* anything reaches the SSE broker, so every event a live
        client observes is already durable and replayable from
        GET /agent/runs/{run_id}/events. A broker failure can therefore
        never lose an event, only delay one client's view of it.

        `payload` is sanitized on the way in (see events.sanitize_payload),
        so forbidden keys -- credentials, prompts, reasoning traces -- are
        not merely hidden from the stream, they are never written to the
        audit trail at all.
        """
        current = db.scalar(
            select(AgentEvent.seq)
            .where(AgentEvent.agent_run_id == agent_run_id)
            .order_by(AgentEvent.seq.desc())
            .limit(1)
        )
        event = AgentEvent(
            agent_run_id=agent_run_id,
            workspace_id=workspace_id,
            seq=(current or 0) + 1,
            event_type=event_type,
            payload_json=sanitize_payload(payload),
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        run_row = db.execute(
            select(AgentRun.public_id, AgentRun.trace_id).where(AgentRun.id == agent_run_id)
        ).first()
        public_id = run_public_id or (run_row[0] if run_row else None)
        if public_id:
            try:
                get_event_broker().publish(
                    LiveAgentEvent(
                        run_public_id=public_id,
                        seq=event.seq,
                        event_type=event.event_type,
                        payload=event.payload_json,
                        created_at=event.created_at,
                        workspace_id=workspace_id,
                        event_id=event.public_id,
                        trace_id=run_row[1] if run_row else None,
                    )
                )
            except Exception:  # noqa: BLE001 - the row is committed; only liveness is lost
                # A transport outage must never fail the run: the event is
                # already durable and every stream replays from the database.
                logger.warning(
                    "agent_event.publish_failed run=%s seq=%s", public_id, event.seq, exc_info=True
                )
        return event

    def list_events(self, db: Session, agent_run_id: int) -> list[AgentEvent]:
        statement = (
            select(AgentEvent)
            .where(AgentEvent.agent_run_id == agent_run_id)
            .order_by(AgentEvent.seq.asc())
        )
        return list(db.scalars(statement))

    def create_action(
        self,
        db: Session,
        *,
        workspace_id: int,
        agent_run_id: int,
        tool_call_id: int | None,
        tool_name: str,
        resource_type: str,
        resource_id: str,
        payload: dict[str, Any],
        payload_hash: str,
        preview: dict[str, Any],
        risk_level: str,
        expires_at: datetime,
        idempotency_key: str,
        trace_id: str,
    ) -> AgentAction:
        action = AgentAction(
            workspace_id=workspace_id,
            agent_run_id=agent_run_id,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            resource_type=resource_type,
            resource_id=resource_id,
            payload_json=payload,
            payload_hash=payload_hash,
            preview_json=preview,
            risk_level=risk_level,
            status="pending",
            expires_at=expires_at,
            idempotency_key=idempotency_key,
            trace_id=trace_id,
        )
        db.add(action)
        db.commit()
        db.refresh(action)
        return action

    def get_action_by_public_id(
        self, db: Session, *, workspace_id: int, action_id: str
    ) -> AgentAction | None:
        statement = select(AgentAction).where(
            AgentAction.workspace_id == workspace_id, AgentAction.public_id == action_id
        )
        return db.scalar(statement)

    def list_actions(
        self,
        db: Session,
        *,
        workspace_id: int,
        status: str | None,
        page: int,
        per_page: int,
        agent_run_id: int | None = None,
    ) -> tuple[list[AgentAction], int]:
        filters = [AgentAction.workspace_id == workspace_id]
        if agent_run_id is not None:
            filters.append(AgentAction.agent_run_id == agent_run_id)
        if status is not None:
            filters.append(AgentAction.status == status)
        from sqlalchemy import func

        total = int(db.scalar(select(func.count(AgentAction.id)).where(*filters)) or 0)
        statement = (
            select(AgentAction)
            .where(*filters)
            .order_by(AgentAction.created_at.desc(), AgentAction.id.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        return list(db.scalars(statement)), total

    def claim_action_for_decision(
        self,
        db: Session,
        *,
        workspace_id: int,
        action_id: int,
        new_status: str,
    ) -> bool:
        """Atomically transition a pending action, returning True iff this
        call won the race (i.e. the row was still 'pending' the instant this
        UPDATE executed). A losing caller must not proceed to execute or
        re-decide the action -- rowcount == 0 means someone else already
        claimed it, or it already expired/was rejected.
        """
        result = cast(
            "CursorResult[Any]",
            db.execute(
                update(AgentAction)
                .where(
                    AgentAction.id == action_id,
                    AgentAction.workspace_id == workspace_id,
                    AgentAction.status == "pending",
                )
                .values(status=new_status, updated_at=datetime.now(tz=UTC))
            ),
        )
        db.commit()
        return bool(result.rowcount and result.rowcount > 0)

    def finalize_action(
        self,
        db: Session,
        action: AgentAction,
        *,
        status: str,
        result: dict[str, Any] | None = None,
        failure_code: str | None = None,
        failure_message: str | None = None,
        approved_by_user_id: int | None = None,
        approved_at: datetime | None = None,
        executed_at: datetime | None = None,
    ) -> AgentAction:
        action.status = status
        if result is not None:
            action.result_json = result
        if failure_code is not None:
            action.failure_code = failure_code
        if failure_message is not None:
            action.failure_message = failure_message
        if approved_by_user_id is not None:
            action.approved_by_user_id = approved_by_user_id
        if approved_at is not None:
            action.approved_at = approved_at
        if executed_at is not None:
            action.executed_at = executed_at
        db.add(action)
        db.commit()
        db.refresh(action)
        return action

    def list_pending_actions_for_run(self, db: Session, agent_run_id: int) -> list[AgentAction]:
        statement = select(AgentAction).where(
            AgentAction.agent_run_id == agent_run_id, AgentAction.status == "pending"
        )
        return list(db.scalars(statement))


__all__ = ["AgentRepository"]
