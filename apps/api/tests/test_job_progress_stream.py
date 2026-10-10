from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator

import pytest

from app.core import progress_bus
from app.modules.agents.events import InMemoryAgentEventBroker, set_event_broker
from app.modules.search_jobs.stream import live_stream, terminal_stream


@pytest.fixture(autouse=True)
def _fresh_broker() -> Iterator[None]:
    set_event_broker(InMemoryAgentEventBroker())
    progress_bus.reset()
    yield
    set_event_broker(None)
    progress_bus.reset()


async def _collect(stream: AsyncIterator[str]) -> list[str]:
    return [frame async for frame in stream]


def test_emit_reaches_every_subscriber_and_unsubscribe_is_independent() -> None:
    first = progress_bus.subscribe("job_1", 7)
    second = progress_bus.subscribe("job_1", 7)

    progress_bus.emit("job_1", "fetching", 5, "start", workspace_id=7)
    assert first.get_nowait().payload["stage"] == "fetching"
    assert second.get_nowait().payload["stage"] == "fetching"

    # One viewer leaving must not tear down the other (old per-job queue did).
    progress_bus.unsubscribe("job_1", first)
    progress_bus.emit("job_1", "scoring", 95, "scoring", workspace_id=7)
    assert second.get_nowait().payload["stage"] == "scoring"


def test_last_event_is_workspace_scoped() -> None:
    progress_bus.emit("job_2", "fetching", 40, "x", workspace_id=1)
    assert progress_bus.last_event("job_2", 1) is not None
    assert progress_bus.last_event("job_2", 2) is None


def test_late_subscriber_gets_snapshot_then_closes_on_terminal() -> None:
    progress_bus.emit("job_3", "fetching", 40, "x", workspace_id=1)
    progress_bus.emit("job_3", "done", 100, "ok", workspace_id=1)

    frames = asyncio.run(_collect(live_stream("job_3", 1)))

    assert len(frames) == 1
    assert '"stage": "done"' in frames[0]
    assert frames[0].startswith("id: 2\n")


def test_live_stream_delivers_events_emitted_after_connect() -> None:
    async def scenario() -> list[str]:
        progress_bus.emit("job_4", "fetching", 5, "start", workspace_id=1)
        task = asyncio.create_task(_collect(live_stream("job_4", 1)))
        await asyncio.sleep(0.2)
        progress_bus.emit("job_4", "scoring", 95, "scoring", workspace_id=1)
        progress_bus.emit("job_4", "done", 100, "ok", workspace_id=1)
        return await asyncio.wait_for(task, timeout=10)

    frames = asyncio.run(scenario())
    stages = [f.split('"stage": "')[1].split('"')[0] for f in frames]
    assert stages == ["fetching", "scoring", "done"]


def test_terminal_stream_maps_failure() -> None:
    frames = asyncio.run(_collect(terminal_stream("failed")))
    assert '"stage": "error"' in frames[0]
    assert '"progress": 0' in frames[0]
