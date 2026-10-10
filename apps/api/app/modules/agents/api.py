import logging
import queue
import time
from collections.abc import Iterator

from fastapi import APIRouter, Depends, Header, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import NotFoundError
from app.modules.agents.action_gate import AgentActionGate
from app.modules.agents.events import (
    HEARTBEAT,
    STREAM_CLOSING_EVENT_TYPES,
    BrokerUnavailableError,
    LiveAgentEvent,
    get_event_broker,
)
from app.modules.agents.models import AgentAction, AgentRun
from app.modules.agents.repository import AgentRepository
from app.modules.agents.runtime import AgentRuntime
from app.modules.agents.schemas import (
    AgentActionListResponse,
    AgentActionRejectRequest,
    AgentActionResponse,
    AgentEventListResponse,
    AgentEventResponse,
    AgentRunCreateRequest,
    AgentRunResponse,
)
from app.modules.auth.permissions import assert_workspace_permission
from app.modules.auth.policies import get_current_user, get_current_workspace_id
from app.modules.leads.repository import LeadsRepository
from app.modules.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])

_repository = AgentRepository()
_runtime = AgentRuntime(repository=_repository)
_action_gate = AgentActionGate(repository=_repository)
_leads_repository = LeadsRepository()


def _run_to_response(run: AgentRun) -> AgentRunResponse:
    return AgentRunResponse(
        run_id=run.public_id,
        status=run.status,  # type: ignore[arg-type]
        profile=run.profile,
        stop_reason=run.stop_reason,
        lead_id=None,
        goal=run.goal,
        step_count=run.step_count,
        tool_call_count=run.tool_call_count,
        external_search_count=run.external_search_count,
        crawl_count=run.crawl_count,
        write_proposal_count=run.write_proposal_count,
        final_answer=run.final_answer_json,
        error_code=run.error_code,
        error_message=run.error_message,
        created_at=run.created_at,
        updated_at=run.updated_at,
        completed_at=run.completed_at,
    )


def _action_to_response(db: Session, action: AgentAction) -> AgentActionResponse:
    # The public run id, never the internal integer key: a client correlates an
    # action with the run it belongs to (and its SSE stream) by this value.
    run = db.get(AgentRun, action.agent_run_id)
    return AgentActionResponse(
        action_id=action.public_id,
        run_id=run.public_id if run is not None else "",
        tool_name=action.tool_name,
        resource_type=action.resource_type,
        resource_id=action.resource_id,
        preview=action.preview_json,
        risk_level=action.risk_level,  # type: ignore[arg-type]
        status=action.status,  # type: ignore[arg-type]
        result=action.result_json,
        failure_code=action.failure_code,
        failure_message=action.failure_message,
        expires_at=action.expires_at,
        approved_at=action.approved_at,
        executed_at=action.executed_at,
        created_at=action.created_at,
    )


@router.post("/runs", response_model=AgentRunResponse, status_code=status.HTTP_201_CREATED)
def create_run(
    payload: AgentRunCreateRequest,
    db: Session = Depends(get_db),
    workspace_id: int = Depends(get_current_workspace_id),
    current_user: User = Depends(get_current_user),
) -> AgentRunResponse:
    lead = None
    if payload.lead_id is not None:
        lead = _leads_repository.get_by_public_id_for_workspace(
            db, workspace_id=workspace_id, public_id=payload.lead_id
        )
        if lead is None:
            raise NotFoundError("Lead was not found.")
    run = _runtime.start(
        db,
        workspace_id=workspace_id,
        lead=lead,
        current_user=current_user,
        goal=payload.goal,
        profile_key=payload.profile,
    )
    response = _run_to_response(run)
    response.lead_id = payload.lead_id
    return response


def _get_run_or_raise(db: Session, *, workspace_id: int, run_id: str) -> AgentRun:
    run = _repository.get_run_by_public_id(db, workspace_id=workspace_id, run_id=run_id)
    if run is None:
        raise NotFoundError("Agent run was not found.")
    return run


@router.get("/runs/{run_id}", response_model=AgentRunResponse)
def get_run(
    run_id: str,
    db: Session = Depends(get_db),
    workspace_id: int = Depends(get_current_workspace_id),
) -> AgentRunResponse:
    run = _get_run_or_raise(db, workspace_id=workspace_id, run_id=run_id)
    response = _run_to_response(run)
    if run.lead_id is not None:
        lead = _leads_repository.get_by_id_for_workspace(
            db, workspace_id=workspace_id, lead_id=run.lead_id
        )
        response.lead_id = lead.public_id if lead is not None else None
    return response


@router.get("/runs/{run_id}/events", response_model=AgentEventListResponse)
def list_run_events(
    run_id: str,
    db: Session = Depends(get_db),
    workspace_id: int = Depends(get_current_workspace_id),
) -> AgentEventListResponse:
    run = _get_run_or_raise(db, workspace_id=workspace_id, run_id=run_id)
    events = _repository.list_events(db, run.id)
    return AgentEventListResponse(
        run_id=run.public_id,
        events=[
            AgentEventResponse(
                event_id=event.public_id,
                seq=event.seq,
                event_type=event.event_type,
                payload=event.payload_json,
                created_at=event.created_at,
            )
            for event in events
        ],
    )


def _stream_events(
    *,
    run_public_id: str,
    channel: "queue.Queue[LiveAgentEvent] | None",
    replay: list[LiveAgentEvent],
    run_already_closed: bool,
) -> Iterator[str]:
    """Yield the SSE body: persisted replay first, then live events.

    The subscription is opened by the caller *before* the replay is read
    from the database, so an event produced between the two cannot fall
    through the crack -- it lands in `channel` and is de-duplicated here
    against the replayed sequence numbers.
    """
    settings = get_settings()
    broker = get_event_broker()
    deadline = time.monotonic() + settings.agent_stream_max_seconds
    highest_seq = 0
    try:
        for event in replay:
            highest_seq = max(highest_seq, event.seq)
            yield event.as_sse()

        if run_already_closed:
            return
        if channel is None:
            # Live transport unavailable: the client got everything durable
            # so far and reconnects with Last-Event-ID to continue.
            return

        while time.monotonic() < deadline:
            try:
                live = channel.get(timeout=settings.agent_stream_heartbeat_seconds)
            except queue.Empty:
                yield LiveAgentEvent(
                    run_public_id=run_public_id, seq=highest_seq, event_type=HEARTBEAT
                ).as_sse()
                continue
            if live.seq <= highest_seq:
                continue  # already delivered during replay
            highest_seq = live.seq
            yield live.as_sse()
            if live.event_type in STREAM_CLOSING_EVENT_TYPES:
                return
    finally:
        if channel is not None:
            broker.unsubscribe(run_public_id, channel)


@router.get("/runs/{run_id}/stream")
def stream_run_events(
    run_id: str,
    after_seq: int = Query(default=0, ge=0),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    db: Session = Depends(get_db),
    workspace_id: int = Depends(get_current_workspace_id),
) -> StreamingResponse:
    """Live Server-Sent Events for one agent run.

    Authorization is enforced here, once, against the caller's workspace:
    a run belonging to another workspace 404s exactly as the other run
    endpoints do, and the workspace is never taken from the query string.

    Reconnect is lossless and duplicate-free: the resume point is the
    larger of `after_seq` and the standard `Last-Event-ID` header (the SSE
    `id:` of each event is its persisted seq). The live subscription is
    opened BEFORE persisted history is read, so an event committed in
    between arrives on the channel and is de-duplicated by seq.
    """
    run = _get_run_or_raise(db, workspace_id=workspace_id, run_id=run_id)
    resume_after = after_seq
    if last_event_id and last_event_id.strip().isdigit():
        resume_after = max(resume_after, int(last_event_id.strip()))

    broker = get_event_broker()
    channel: queue.Queue[LiveAgentEvent] | None
    try:
        # Subscribe before reading history so no event can slip between the two.
        channel = broker.subscribe(run.public_id, run.workspace_id)
    except BrokerUnavailableError:
        logger.warning("agent_stream.broker_unavailable run=%s; replay only", run.public_id)
        channel = None
    try:
        replay = [
            LiveAgentEvent(
                run_public_id=run.public_id,
                seq=event.seq,
                event_type=event.event_type,
                payload=event.payload_json,
                created_at=event.created_at,
                workspace_id=run.workspace_id,
                event_id=event.public_id,
                trace_id=run.trace_id,
            )
            for event in _repository.list_events(db, run.id)
            if event.seq > resume_after
        ]
        # waiting_for_approval parks the run: no event can follow without a new
        # request, and STREAM_CLOSING_EVENT_TYPES already ends live streams on it.
        closed = run.status in {"completed", "failed", "cancelled", "expired", "waiting_for_approval"}
    except Exception:
        if channel is not None:
            broker.unsubscribe(run.public_id, channel)
        raise

    return StreamingResponse(
        _stream_events(
            run_public_id=run.public_id,
            channel=channel,
            replay=replay,
            run_already_closed=closed,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/runs/{run_id}/cancel", response_model=AgentRunResponse)
def cancel_run(
    run_id: str,
    db: Session = Depends(get_db),
    workspace_id: int = Depends(get_current_workspace_id),
) -> AgentRunResponse:
    run = _runtime.cancel(db, workspace_id=workspace_id, run_id=run_id)
    return _run_to_response(run)


@router.get("/actions", response_model=AgentActionListResponse)
def list_actions(
    status_filter: str | None = Query(default=None, alias="status"),
    run_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    workspace_id: int = Depends(get_current_workspace_id),
) -> AgentActionListResponse:
    agent_run_id: int | None = None
    if run_id is not None:
        run = _repository.get_run_by_public_id(db, workspace_id=workspace_id, run_id=run_id)
        if run is None:
            # An unknown (or foreign) run is indistinguishable from an empty one.
            return AgentActionListResponse(items=[], page=page, per_page=per_page, total=0)
        agent_run_id = run.id
    items, total = _repository.list_actions(
        db,
        workspace_id=workspace_id,
        status=status_filter,
        agent_run_id=agent_run_id,
        page=page,
        per_page=per_page,
    )
    return AgentActionListResponse(
        items=[_action_to_response(db, action) for action in items],
        page=page,
        per_page=per_page,
        total=total,
    )


def _get_action_or_raise(db: Session, *, workspace_id: int, action_id: str) -> AgentAction:
    action = _repository.get_action_by_public_id(db, workspace_id=workspace_id, action_id=action_id)
    if action is None:
        raise NotFoundError("Agent action was not found.")
    return action


@router.get("/actions/{action_id}", response_model=AgentActionResponse)
def get_action(
    action_id: str,
    db: Session = Depends(get_db),
    workspace_id: int = Depends(get_current_workspace_id),
) -> AgentActionResponse:
    action = _get_action_or_raise(db, workspace_id=workspace_id, action_id=action_id)
    return _action_to_response(db, action)


@router.post("/actions/{action_id}/approve", response_model=AgentActionResponse)
def approve_action(
    action_id: str,
    db: Session = Depends(get_db),
    workspace_id: int = Depends(get_current_workspace_id),
    current_user: User = Depends(get_current_user),
) -> AgentActionResponse:
    assert_workspace_permission(
        current_user.role, "leads:manage", message="Insufficient role to approve agent actions."
    )
    action = _action_gate.approve(
        db, workspace_id=workspace_id, action_id=action_id, current_user=current_user
    )
    _runtime.resume_after_action(
        db, workspace_id=workspace_id, run_id=action.agent_run_id, current_user=current_user
    )
    db.refresh(action)
    return _action_to_response(db, action)


@router.post("/actions/{action_id}/reject", response_model=AgentActionResponse)
def reject_action(
    action_id: str,
    payload: AgentActionRejectRequest,
    db: Session = Depends(get_db),
    workspace_id: int = Depends(get_current_workspace_id),
    current_user: User = Depends(get_current_user),
) -> AgentActionResponse:
    assert_workspace_permission(
        current_user.role, "leads:manage", message="Insufficient role to reject agent actions."
    )
    action = _action_gate.reject(
        db,
        workspace_id=workspace_id,
        action_id=action_id,
        current_user=current_user,
        reason=payload.reason,
    )
    _runtime.resume_after_action(
        db, workspace_id=workspace_id, run_id=action.agent_run_id, current_user=current_user
    )
    db.refresh(action)
    return _action_to_response(db, action)


__all__ = ["router"]
