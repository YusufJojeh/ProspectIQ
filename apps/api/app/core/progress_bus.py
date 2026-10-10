"""Search-job progress events, carried over the shared agent EventBroker.

Producers (the discovery orchestrator) call `emit`; SSE endpoints call
`subscribe` / `unsubscribe`. Transport, fan-out and cross-worker delivery
(in-memory or Redis, selected by AGENT_EVENT_BROKER) are delegated to
`app.modules.agents.events`, so many viewers can follow one job at once and
one viewer disconnecting never tears down another's subscription.

Pub/sub is fire-and-forget, so the latest event per job is also remembered
in-process (`last_event`). A client that connects or reconnects mid-job is
sent that snapshot first. With the Redis broker the snapshot only exists on
the worker that ran the job; other workers fall back to live events plus the
persisted job status, which the SSE endpoint checks before subscribing.
"""

from __future__ import annotations

import logging
import queue
import threading
from collections import OrderedDict
from typing import Any

from app.modules.agents.events import LiveAgentEvent, get_event_broker

logger = logging.getLogger(__name__)

JOB_PROGRESS = "job_progress"
TERMINAL_STAGES: frozenset[str] = frozenset({"done", "error"})

_MAX_TRACKED_JOBS = 1000

_lock = threading.Lock()
_seq: OrderedDict[str, int] = OrderedDict()
_last: OrderedDict[str, LiveAgentEvent] = OrderedDict()


def _channel_key(job_id: str) -> str:
    # Namespaced so a job id can never collide with an agent run id.
    return f"searchjob:{job_id}"


def emit(
    job_id: str,
    stage: str,
    progress: int,
    message: str,
    *,
    workspace_id: int | None = None,
) -> None:
    key = _channel_key(job_id)
    with _lock:
        seq = _seq.get(key, 0) + 1
        _seq[key] = seq
        _seq.move_to_end(key)
        while len(_seq) > _MAX_TRACKED_JOBS:
            _seq.popitem(last=False)
        event = LiveAgentEvent(
            run_public_id=key,
            seq=seq,
            event_type=JOB_PROGRESS,
            payload={"stage": stage, "progress": progress, "message": message},
            workspace_id=workspace_id,
        )
        _last[key] = event
        _last.move_to_end(key)
        while len(_last) > _MAX_TRACKED_JOBS:
            _last.popitem(last=False)
    get_event_broker().publish(event)


def subscribe(job_id: str, workspace_id: int) -> queue.Queue[LiveAgentEvent]:
    """Open a live channel. Raises BrokerUnavailableError if the transport is down."""
    return get_event_broker().subscribe(_channel_key(job_id), workspace_id)


def unsubscribe(job_id: str, channel: queue.Queue[LiveAgentEvent]) -> None:
    get_event_broker().unsubscribe(_channel_key(job_id), channel)


def last_event(job_id: str, workspace_id: int) -> LiveAgentEvent | None:
    """Latest event for the job, or None. Scoped: another tenant's event is never returned."""
    with _lock:
        event = _last.get(_channel_key(job_id))
    if event is None or event.workspace_id != workspace_id:
        return None
    return event


def to_wire(event: LiveAgentEvent) -> dict[str, Any]:
    """The `{stage, progress, message}` shape the browser consumes."""
    payload = event.payload
    return {
        "stage": str(payload.get("stage", "")),
        "progress": int(payload.get("progress", 0)),
        "message": str(payload.get("message", "")),
    }


def reset() -> None:
    """Test hook: forget all tracked jobs."""
    with _lock:
        _seq.clear()
        _last.clear()
