"""SSE body for search-job progress, shared by the v1 and v2 stream routes."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from queue import Empty

from app.core import progress_bus
from app.modules.agents.events import BrokerUnavailableError

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}
TERMINAL_STATUSES = frozenset({"completed", "partially_completed", "failed"})
SSE_TIMEOUT_TICKS = 300  # 1 s per tick -> 5-minute max stream

WireMapper = Callable[[dict[str, object]], dict[str, object]]


def _identity(wire: dict[str, object]) -> dict[str, object]:
    return wire


def _frame(wire: dict[str, object], seq: int | None = None) -> str:
    prefix = f"id: {seq}\n" if seq is not None else ""
    return f"{prefix}data: {json.dumps(wire)}\n\n"


async def terminal_stream(
    status: str, *, map_wire: WireMapper = _identity, failed_stage: str = "error"
) -> AsyncIterator[str]:
    ok = status in ("completed", "partially_completed")
    stage = "done" if ok else failed_stage
    yield _frame(map_wire({"stage": stage, "progress": 100 if ok else 0, "message": status}))


async def live_stream(
    job_id: str, workspace_id: int, *, map_wire: WireMapper = _identity
) -> AsyncIterator[str]:
    """Snapshot of the latest known event, then live events until done/error.

    Subscribes BEFORE reading the snapshot so an event emitted in between is
    delivered on the channel instead of being lost; duplicates are dropped
    by seq.
    """
    try:
        channel = progress_bus.subscribe(job_id, workspace_id)
    except BrokerUnavailableError:
        yield ": broker-unavailable\n\n"
        return

    try:
        highest_seq = 0
        snapshot = progress_bus.last_event(job_id, workspace_id)
        if snapshot is not None:
            highest_seq = snapshot.seq
            wire = progress_bus.to_wire(snapshot)
            yield _frame(map_wire(dict(wire)), snapshot.seq)
            if wire["stage"] in progress_bus.TERMINAL_STAGES:
                return

        idle_ticks = 0
        while idle_ticks < SSE_TIMEOUT_TICKS:
            try:
                event = await asyncio.to_thread(channel.get, True, 1.0)
            except Empty:
                idle_ticks += 1
                yield ": keepalive\n\n"
                continue
            idle_ticks = 0
            if event.seq <= highest_seq:
                continue
            highest_seq = event.seq
            wire = progress_bus.to_wire(event)
            yield _frame(map_wire(dict(wire)), event.seq)
            if wire["stage"] in progress_bus.TERMINAL_STAGES:
                return
    finally:
        progress_bus.unsubscribe(job_id, channel)
