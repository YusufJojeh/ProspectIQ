from __future__ import annotations

import json
import threading
import time

from test_workspace_e2e import _build_session_factory, _login, _override_client, _seed_workspace

from app.core.config import clear_settings_cache
from app.modules.agents.events import (
    AGENT_COMPLETED,
    HEARTBEAT,
    TOOL_STARTED,
    AgentEventBroker,
    LiveAgentEvent,
    get_event_broker,
    sanitize_payload,
)


def _use_stub_runtime(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("TAVILY_RUNTIME_MODE", "demo")
    monkeypatch.setenv("APIFY_RUNTIME_MODE", "demo")
    clear_settings_cache()


def _parse_sse(body: str) -> list[dict[str, object]]:
    """Parse an SSE body into its decoded `data:` payloads."""
    frames: list[dict[str, object]] = []
    for block in body.split("\n\n"):
        for line in block.splitlines():
            if line.startswith("data: "):
                frames.append(json.loads(line[len("data: ") :]))
    return frames


# --- Broker unit behaviour ---------------------------------------------


def test_broker_fans_out_to_every_subscriber_and_unsubscribes_cleanly() -> None:
    broker = AgentEventBroker()
    first = broker.subscribe("arun_1")
    second = broker.subscribe("arun_1")
    other_run = broker.subscribe("arun_2")

    broker.publish(LiveAgentEvent(run_public_id="arun_1", seq=1, event_type=TOOL_STARTED))

    assert first.get_nowait().seq == 1
    assert second.get_nowait().seq == 1
    assert other_run.empty(), "an event must never leak into another run's channel"

    broker.unsubscribe("arun_1", first)
    assert broker.subscriber_count("arun_1") == 1
    broker.unsubscribe("arun_1", second)
    assert broker.subscriber_count("arun_1") == 0


def test_broker_does_not_block_when_a_subscriber_stops_draining() -> None:
    """A stalled client must never stall the agent loop."""
    broker = AgentEventBroker(max_queue_size=2)
    broker.subscribe("arun_slow")
    for seq in range(1, 20):
        broker.publish(LiveAgentEvent(run_public_id="arun_slow", seq=seq, event_type=HEARTBEAT))
    # Reaching here without blocking or raising is the assertion.
    assert broker.subscriber_count("arun_slow") == 1


def test_sanitize_payload_strips_secrets_and_reasoning_before_persistence() -> None:
    cleaned = sanitize_payload(
        {
            "tool_name": "search_web_tavily",
            "api_key": "sk-live-should-never-persist",
            "reasoning": "step 1 the model thought...",
            "chain_of_thought": "hidden",
            "system_prompt": "You are...",
            "nested": {"token": "abc", "status": "ok"},
            "long": "x" * 5000,
        }
    )
    assert cleaned["tool_name"] == "search_web_tavily"
    assert "api_key" not in cleaned
    assert "reasoning" not in cleaned
    assert "chain_of_thought" not in cleaned
    assert "system_prompt" not in cleaned
    assert cleaned["nested"] == {"status": "ok"}
    assert len(str(cleaned["long"])) < 5000


# --- Live SSE endpoint --------------------------------------------------


def test_stream_replays_persisted_events_and_closes_on_finished_run(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A finished run's stream is pure replay: every persisted event, in
    order, then EOF -- no hanging connection."""
    _use_stub_runtime(monkeypatch)
    get_event_broker().reset()
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        headers = {"Authorization": f"Bearer {token}"}
        run_id = client.post(
            "/api/v1/agent/runs",
            json={"goal": "Analyse this lead.", "lead_id": seed.lead_public_id},
            headers=headers,
        ).json()["run_id"]

        # Drive the run to a terminal state by rejecting the pending action.
        action_id = client.get(
            "/api/v1/agent/actions", params={"status": "pending"}, headers=headers
        ).json()["items"][0]["action_id"]
        client.post(
            f"/api/v1/agent/actions/{action_id}/reject", json={"reason": "no"}, headers=headers
        )
        # Reject the second proposal too so the run completes.
        remaining = client.get(
            "/api/v1/agent/actions", params={"status": "pending"}, headers=headers
        ).json()["items"]
        for action in remaining:
            client.post(
                f"/api/v1/agent/actions/{action['action_id']}/reject",
                json={"reason": "no"},
                headers=headers,
            )

        response = client.get(f"/api/v1/agent/runs/{run_id}/stream", headers=headers)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

        frames = _parse_sse(response.text)
        assert frames, "a finished run must still replay its persisted events"
        seqs = [frame["seq"] for frame in frames]
        assert seqs == sorted(seqs), "events must stream in persisted order"
        types = {frame["event_type"] for frame in frames}
        assert "agent_started" in types
        assert "tool_requested" in types
        assert "action_proposed" in types


def test_stream_after_seq_resumes_without_re_delivering_known_events(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _use_stub_runtime(monkeypatch)
    get_event_broker().reset()
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        headers = {"Authorization": f"Bearer {token}"}
        run_id = client.post(
            "/api/v1/agent/runs",
            json={"goal": "Analyse this lead.", "lead_id": seed.lead_public_id},
            headers=headers,
        ).json()["run_id"]
        for action in client.get(
            "/api/v1/agent/actions", params={"status": "pending"}, headers=headers
        ).json()["items"]:
            client.post(
                f"/api/v1/agent/actions/{action['action_id']}/reject",
                json={"reason": "no"},
                headers=headers,
            )
        for action in client.get(
            "/api/v1/agent/actions", params={"status": "pending"}, headers=headers
        ).json()["items"]:
            client.post(
                f"/api/v1/agent/actions/{action['action_id']}/reject",
                json={"reason": "no"},
                headers=headers,
            )

        full = _parse_sse(client.get(f"/api/v1/agent/runs/{run_id}/stream", headers=headers).text)
        assert len(full) > 3
        cutoff = int(full[2]["seq"])  # type: ignore[call-overload]
        resumed = _parse_sse(
            client.get(
                f"/api/v1/agent/runs/{run_id}/stream",
                params={"after_seq": cutoff},
                headers=headers,
            ).text
        )
        assert all(int(frame["seq"]) > cutoff for frame in resumed)  # type: ignore[call-overload]
        assert len(resumed) == len(full) - 3


def test_stream_is_workspace_scoped(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A run from another workspace 404s on the stream exactly as it does on
    every other run endpoint -- streaming is not a way around tenancy."""
    _use_stub_runtime(monkeypatch)
    get_event_broker().reset()
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        headers = {"Authorization": f"Bearer {token}"}
        run_id = client.post(
            "/api/v1/agent/runs",
            json={"goal": "Analyse this lead.", "lead_id": seed.lead_public_id},
            headers=headers,
        ).json()["run_id"]

        anonymous = client.get(f"/api/v1/agent/runs/{run_id}/stream")
        assert anonymous.status_code == 401

        missing = client.get("/api/v1/agent/runs/arun_does_not_exist/stream", headers=headers)
        assert missing.status_code == 404


def test_stream_delivers_live_events_published_after_subscription() -> None:
    """The broker -> SSE path itself: an event published while a subscriber
    is attached reaches it without the subscriber polling the database."""
    broker = AgentEventBroker()
    received: list[LiveAgentEvent] = []

    with broker.subscription("arun_live") as channel:

        def _publish_soon() -> None:
            time.sleep(0.05)
            broker.publish(
                LiveAgentEvent(run_public_id="arun_live", seq=7, event_type=AGENT_COMPLETED)
            )

        thread = threading.Thread(target=_publish_soon)
        thread.start()
        received.append(channel.get(timeout=5))
        thread.join()

    assert received[0].seq == 7
    assert received[0].event_type == AGENT_COMPLETED
    assert received[0].as_sse().startswith("id: 7\nevent: agent_completed\ndata: ")
