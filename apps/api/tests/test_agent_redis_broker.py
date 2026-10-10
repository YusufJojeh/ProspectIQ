from __future__ import annotations

import json
import queue
import threading
import time
from collections.abc import Iterator
from typing import Any

import pytest
from test_agent_streaming import _parse_sse, _use_stub_runtime
from test_workspace_e2e import _build_session_factory, _login, _override_client, _seed_workspace

from app.core.config import Settings, clear_settings_cache
from app.modules.agents import api as agent_api
from app.modules.agents.events import (
    AGENT_COMPLETED,
    TOOL_STARTED,
    InMemoryAgentEventBroker,
    LiveAgentEvent,
    RedisAgentEventBroker,
    build_event_broker,
    set_event_broker,
)
from app.modules.agents.models import AgentEvent, AgentRun
from app.modules.agents.repository import AgentRepository

# --- A thread-safe Redis pub/sub stand-in --------------------------------
#
# Two RedisAgentEventBroker instances sharing one FakeRedisServer behave
# like two API worker processes talking to one Redis: neither shares any
# Python state with the other except through the "server". No production
# Redis is needed in CI.


class FakeRedisServer:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.channels: dict[str, list[queue.Queue[dict[str, Any]]]] = {}
        self.published: list[tuple[str, str]] = []
        self.down = False

    def check(self) -> None:
        if self.down:
            raise ConnectionError("redis down")


class FakePubSub:
    def __init__(self, server: FakeRedisServer) -> None:
        self.server = server
        self.inbox: queue.Queue[dict[str, Any]] = queue.Queue()
        self.subscribed: list[str] = []

    def subscribe(self, channel: str) -> None:
        self.server.check()
        with self.server.lock:
            self.server.channels.setdefault(channel, []).append(self.inbox)
        self.subscribed.append(channel)

    def get_message(self, timeout: float = 0.0) -> dict[str, Any] | None:
        try:
            return self.inbox.get(timeout=timeout)
        except queue.Empty:
            return None

    def close(self) -> None:
        with self.server.lock:
            for channel in self.subscribed:
                inboxes = self.server.channels.get(channel, [])
                if self.inbox in inboxes:
                    inboxes.remove(self.inbox)


class FakeRedis:
    def __init__(self, server: FakeRedisServer) -> None:
        self.server = server

    def publish(self, channel: str, data: str) -> int:
        self.server.check()
        with self.server.lock:
            self.server.published.append((channel, data))
            targets = list(self.server.channels.get(channel, []))
        for inbox in targets:
            inbox.put({"type": "message", "channel": channel, "data": data})
        return len(targets)

    def pubsub(self, ignore_subscribe_messages: bool = True) -> FakePubSub:
        return FakePubSub(self.server)

    def ping(self) -> bool:
        # Boot-time reachability only; outages under test start after boot.
        return True


@pytest.fixture
def two_workers() -> Iterator[tuple[FakeRedisServer, RedisAgentEventBroker, RedisAgentEventBroker]]:
    server = FakeRedisServer()
    worker_a = RedisAgentEventBroker(FakeRedis(server))
    worker_b = RedisAgentEventBroker(FakeRedis(server))
    yield server, worker_a, worker_b
    worker_a.reset()
    worker_b.reset()
    set_event_broker(None)


def _event(run: str, seq: int, workspace_id: int = 1, event_type: str = TOOL_STARTED) -> LiveAgentEvent:
    return LiveAgentEvent(run_public_id=run, seq=seq, event_type=event_type, workspace_id=workspace_id)


def _next(channel: queue.Queue[LiveAgentEvent], timeout: float = 2.0) -> LiveAgentEvent:
    return channel.get(timeout=timeout)


def _stub_run(session_factory: Any, seed: Any) -> tuple[str, int, int]:
    with _override_client(session_factory) as client:
        headers = {"Authorization": f"Bearer {_login(client, seed)}"}
        run = client.post(
            "/api/v1/agent/runs",
            json={"goal": "Research this lead.", "lead_id": seed.lead_public_id},
            headers=headers,
        ).json()
    with session_factory() as db:
        row = db.query(AgentRun).filter_by(public_id=run["run_id"]).one()
        return row.public_id, row.id, row.workspace_id


# 1 ---------------------------------------------------------------------------
def test_event_published_on_worker_a_reaches_subscriber_on_worker_b(two_workers: Any) -> None:
    _, worker_a, worker_b = two_workers
    channel = worker_b.subscribe("arun_x", 7)

    worker_a.publish(_event("arun_x", 1, workspace_id=7))

    received = _next(channel)
    assert (received.run_public_id, received.seq, received.workspace_id) == ("arun_x", 1, 7)
    assert worker_a.subscriber_count("arun_x") == 0, "worker A holds no local subscriber"


def test_repository_add_event_on_worker_a_streams_to_worker_b(
    monkeypatch: pytest.MonkeyPatch, two_workers: Any
) -> None:
    _, worker_a, worker_b = two_workers
    _use_stub_runtime(monkeypatch)
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    run_public_id, run_id, workspace_id = _stub_run(session_factory, seed)
    channel = worker_b.subscribe(run_public_id, workspace_id)

    set_event_broker(worker_a)
    with session_factory() as db:
        persisted = AgentRepository().add_event(
            db, agent_run_id=run_id, workspace_id=workspace_id, event_type=TOOL_STARTED
        )
        trace_id = db.get(AgentRun, run_id).trace_id  # type: ignore[union-attr]

    received = _next(channel)
    assert received.seq == persisted.seq
    assert received.event_id == persisted.public_id
    assert received.trace_id == trace_id


# 2 ---------------------------------------------------------------------------
def test_two_runs_stay_isolated(two_workers: Any) -> None:
    _, worker_a, worker_b = two_workers
    run_one = worker_b.subscribe("arun_1", 1)
    run_two = worker_b.subscribe("arun_2", 1)

    worker_a.publish(_event("arun_1", 1))

    assert _next(run_one).run_public_id == "arun_1"
    time.sleep(0.3)
    assert run_two.empty()


# 3 ---------------------------------------------------------------------------
def test_two_workspaces_stay_isolated_even_for_the_same_run_id(two_workers: Any) -> None:
    server, worker_a, worker_b = two_workers
    tenant_one = worker_b.subscribe("arun_same", 1)
    tenant_two = worker_b.subscribe("arun_same", 2)

    worker_a.publish(_event("arun_same", 1, workspace_id=1))
    assert _next(tenant_one).workspace_id == 1
    time.sleep(0.3)
    assert tenant_two.empty()

    # A message forged onto tenant two's channel but claiming tenant one's
    # scope is rejected by the subscriber's scope check.
    forged = _event("arun_same", 2, workspace_id=1).to_wire()
    FakeRedis(server).publish("prospectiq:agent:2:arun_same", forged)
    time.sleep(0.3)
    assert tenant_two.empty()


# 4 + 5 -----------------------------------------------------------------------
def test_publish_failure_still_persists_the_event_and_the_run_completes(
    monkeypatch: pytest.MonkeyPatch, two_workers: Any
) -> None:
    server, worker_a, _ = two_workers
    _use_stub_runtime(monkeypatch)
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    server.down = True
    set_event_broker(worker_a)

    # A full agent run -- dozens of publishes -- with Redis down throughout.
    run_public_id, run_id, workspace_id = _stub_run(session_factory, seed)

    with session_factory() as db:
        run = db.get(AgentRun, run_id)
        assert run is not None and run.status in {"waiting_for_approval", "completed"}
        seqs = [row.seq for row in db.query(AgentEvent).filter_by(agent_run_id=run_id).order_by(AgentEvent.seq)]
    assert seqs and seqs == list(range(1, len(seqs) + 1)), "every event durable, gap-free"
    assert server.published == []


def test_stream_degrades_to_replay_when_the_broker_cannot_subscribe(
    monkeypatch: pytest.MonkeyPatch, two_workers: Any
) -> None:
    server, worker_a, _ = two_workers
    _use_stub_runtime(monkeypatch)
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    run_public_id, run_id, _ = _stub_run(session_factory, seed)
    server.down = True
    set_event_broker(worker_a)

    with _override_client(session_factory) as client:
        headers = {"Authorization": f"Bearer {_login(client, seed)}"}
        response = client.get(f"/api/v1/agent/runs/{run_public_id}/stream", headers=headers)

    assert response.status_code == 200
    frames = _parse_sse(response.text)
    with session_factory() as db:
        persisted = db.query(AgentEvent).filter_by(agent_run_id=run_id).count()
    assert len(frames) == persisted


# 6 ---------------------------------------------------------------------------
def test_reconnect_with_last_event_id_replays_only_missed_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_stub_runtime(monkeypatch)
    set_event_broker(InMemoryAgentEventBroker())
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    run_public_id, run_id, _ = _stub_run(session_factory, seed)
    with session_factory() as db:
        total = db.query(AgentEvent).filter_by(agent_run_id=run_id).count()
    assert total > 3

    with _override_client(session_factory) as client:
        headers = {"Authorization": f"Bearer {_login(client, seed)}", "Last-Event-ID": "3"}
        response = client.get(f"/api/v1/agent/runs/{run_public_id}/stream", headers=headers)
    set_event_broker(None)

    seqs = [int(str(frame["seq"])) for frame in _parse_sse(response.text)]
    assert seqs == list(range(4, total + 1))
    ids = [line[4:] for line in response.text.splitlines() if line.startswith("id: ")]
    assert ids == [str(seq) for seq in seqs], "SSE id: is the seq a client echoes back"


# 7 ---------------------------------------------------------------------------
def test_replay_and_live_overlap_never_duplicates_an_event(monkeypatch: pytest.MonkeyPatch) -> None:
    """Events committed between subscribe and the history read arrive on
    BOTH paths; the stream must emit each seq exactly once."""
    broker = InMemoryAgentEventBroker()
    set_event_broker(broker)
    try:
        channel = broker.subscribe("arun_o")
        replay = [_event("arun_o", seq) for seq in (1, 2, 3)]
        for seq in (2, 3):
            channel.put(_event("arun_o", seq))
        channel.put(_event("arun_o", 4, event_type=AGENT_COMPLETED))

        body = "".join(
            agent_api._stream_events(
                run_public_id="arun_o", channel=channel, replay=replay, run_already_closed=False
            )
        )
    finally:
        set_event_broker(None)

    assert [frame["seq"] for frame in _parse_sse(body)] == [1, 2, 3, 4]


# 8 ---------------------------------------------------------------------------
def test_heartbeat_is_sent_while_the_run_is_quiet(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_STREAM_HEARTBEAT_SECONDS", "1")
    clear_settings_cache()
    broker = InMemoryAgentEventBroker()
    set_event_broker(broker)
    try:
        channel = broker.subscribe("arun_q")
        stream = agent_api._stream_events(
            run_public_id="arun_q", channel=channel, replay=[], run_already_closed=False
        )
        first = next(stream)
        stream.close()
    finally:
        set_event_broker(None)
        clear_settings_cache()
    assert "event: heartbeat" in first


# 9 ---------------------------------------------------------------------------
def test_terminal_event_ends_the_stream_and_releases_the_subscription(two_workers: Any) -> None:
    _, worker_a, worker_b = two_workers
    set_event_broker(worker_b)
    channel = worker_b.subscribe("arun_t", 1)
    worker_a.publish(_event("arun_t", 1))
    worker_a.publish(_event("arun_t", 2, event_type=AGENT_COMPLETED))

    frames = list(
        agent_api._stream_events(
            run_public_id="arun_t", channel=channel, replay=[], run_already_closed=False
        )
    )

    assert [frame.split("\n")[1] for frame in frames] == ["event: tool_started", "event: agent_completed"]
    assert worker_b.subscriber_count("arun_t") == 0


# 10 --------------------------------------------------------------------------
def test_nothing_private_crosses_the_wire_or_reaches_the_browser(
    monkeypatch: pytest.MonkeyPatch, two_workers: Any
) -> None:
    server, worker_a, _ = two_workers
    _use_stub_runtime(monkeypatch)
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    _, run_id, workspace_id = _stub_run(session_factory, seed)
    set_event_broker(worker_a)

    with session_factory() as db:
        AgentRepository().add_event(
            db,
            agent_run_id=run_id,
            workspace_id=workspace_id,
            event_type=TOOL_STARTED,
            payload={
                "tool_name": "search_web_tavily",
                "api_key": "sk-live-secret",
                "authorization": "Bearer abc",
                "system_prompt": "You are...",
                "reasoning": "hidden thoughts",
                "messages": [{"role": "system"}],
            },
        )

    channel_name, wire = server.published[-1]
    assert channel_name == f"prospectiq:agent:{workspace_id}:" + channel_name.rsplit(":", 1)[1]
    decoded = json.loads(wire)
    assert decoded["payload"] == {"tool_name": "search_web_tavily"}
    for secret in ("sk-live-secret", "Bearer abc", "You are", "hidden thoughts"):
        assert secret not in wire
    browser_frame = LiveAgentEvent.from_wire(wire).as_sse()
    assert "workspace_id" not in browser_frame


# selection -------------------------------------------------------------------
def test_broker_selection_is_explicit_and_never_silently_degrades() -> None:
    assert build_event_broker(Settings(agent_event_broker="inmemory")).multi_worker is False
    with pytest.raises(ValueError, match="REDIS_URL"):
        build_event_broker(Settings(agent_event_broker="redis", redis_url=None))
    redis_broker = build_event_broker(
        Settings(agent_event_broker="redis", redis_url="redis://localhost:6399/0")
    )
    assert isinstance(redis_broker, RedisAgentEventBroker) and redis_broker.multi_worker


def test_production_refuses_the_in_memory_broker_without_an_explicit_single_worker_ack() -> None:
    prod: dict[str, Any] = {
        "app_env": "production",
        "jwt_secret": "x" * 40,
        "default_admin_password": "a-real-password-123",
        # conftest acknowledges single-worker by default; this test is about
        # the unacknowledged case.
        "agent_event_broker_single_worker": False,
    }
    with pytest.raises(ValueError, match="AGENT_EVENT_BROKER=redis"):
        Settings(**prod)
    with pytest.raises(ValueError, match="REDIS_URL"):
        Settings(**prod, agent_event_broker="redis")
    assert Settings(**prod, agent_event_broker="redis", redis_url="redis://r:6379/0")
    assert Settings(**{**prod, "agent_event_broker_single_worker": True})
