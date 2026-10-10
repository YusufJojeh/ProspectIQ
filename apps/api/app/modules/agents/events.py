from __future__ import annotations

import json
import queue
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

# --- Canonical agent lifecycle event vocabulary -------------------------
#
# Every value here may be persisted as an AgentEvent row AND published to
# live subscribers. The two paths are deliberately ordered: persist first,
# publish second (see AgentEventEmitter.emit) so a subscriber can never
# observe an event that is not already durable and replayable from
# GET /agent/runs/{run_id}/events.
#
# No event payload may ever carry chain-of-thought, hidden system prompts,
# provider credentials, or raw untrusted document text. Payloads are
# bounded, structured metadata only.

AGENT_STARTED = "agent_started"
MODEL_STARTED = "model_started"
MODEL_COMPLETED = "model_completed"
ASSISTANT_DELTA = "assistant_delta"
TOOL_REQUESTED = "tool_requested"
TOOL_STARTED = "tool_started"
TOOL_COMPLETED = "tool_completed"
TOOL_FAILED = "tool_failed"
RAG_SEARCH_STARTED = "rag_search_started"
RAG_SEARCH_COMPLETED = "rag_search_completed"
KNOWLEDGE_SELECTED = "knowledge_selected"
ACTION_PROPOSED = "action_proposed"
WAITING_FOR_APPROVAL = "waiting_for_approval"
ACTION_APPROVED = "action_approved"
ACTION_REJECTED = "action_rejected"
ACTION_EXECUTING = "action_executing"
ACTION_COMPLETED = "action_completed"
ACTION_FAILED = "action_failed"
AGENT_RESUMED = "agent_resumed"
AGENT_COMPLETED = "agent_completed"
AGENT_FAILED = "agent_failed"
AGENT_CANCELLED = "agent_cancelled"
BUDGET_EXHAUSTED = "budget_exhausted"
#: Guardrail: the final answer cited evidence this run never observed.
FINAL_EVIDENCE_REF_DROPPED = "final_evidence_ref_dropped"
HEARTBEAT = "heartbeat"

#: Event types after which the live stream may close: the run is either
#: finished or is parked waiting on a human, and no further events will be
#: produced without a new HTTP request.
STREAM_CLOSING_EVENT_TYPES: frozenset[str] = frozenset(
    {AGENT_COMPLETED, AGENT_FAILED, AGENT_CANCELLED, WAITING_FOR_APPROVAL}
)

KNOWN_EVENT_TYPES: frozenset[str] = frozenset(
    {
        AGENT_STARTED,
        MODEL_STARTED,
        MODEL_COMPLETED,
        ASSISTANT_DELTA,
        TOOL_REQUESTED,
        TOOL_STARTED,
        TOOL_COMPLETED,
        TOOL_FAILED,
        RAG_SEARCH_STARTED,
        RAG_SEARCH_COMPLETED,
        KNOWLEDGE_SELECTED,
        ACTION_PROPOSED,
        WAITING_FOR_APPROVAL,
        ACTION_APPROVED,
        ACTION_REJECTED,
        ACTION_EXECUTING,
        ACTION_COMPLETED,
        ACTION_FAILED,
        AGENT_RESUMED,
        AGENT_COMPLETED,
        AGENT_FAILED,
        AGENT_CANCELLED,
        BUDGET_EXHAUSTED,
        FINAL_EVIDENCE_REF_DROPPED,
        HEARTBEAT,
    }
)

# Payload keys that must never leave the server, regardless of which layer
# assembled the payload. Stripped defensively in `sanitize_payload` so a
# future caller cannot accidentally widen what SSE (or the audit log)
# exposes.
_FORBIDDEN_PAYLOAD_KEYS: frozenset[str] = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "chain_of_thought",
        "credentials",
        "messages",
        "password",
        "prompt",
        "raw_content",
        "reasoning",
        "reasoning_content",
        "secret",
        "system_prompt",
        "thinking",
        "token",
    }
)

_MAX_PAYLOAD_VALUE_CHARS = 2000


def sanitize_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Drop forbidden keys and bound string sizes.

    This is the last line of defence between an event producer and both the
    audit log and the live SSE stream: it is applied on the way *in*, so a
    secret or a reasoning trace is never persisted in the first place.
    """
    if not payload:
        return {}
    clean: dict[str, Any] = {}
    for key, value in payload.items():
        if key.lower() in _FORBIDDEN_PAYLOAD_KEYS:
            continue
        if isinstance(value, str) and len(value) > _MAX_PAYLOAD_VALUE_CHARS:
            clean[key] = value[:_MAX_PAYLOAD_VALUE_CHARS] + "...[truncated]"
        elif isinstance(value, dict):
            clean[key] = sanitize_payload(value)
        else:
            clean[key] = value
    return clean


@dataclass(frozen=True, slots=True)
class LiveAgentEvent:
    """One event as it travels over the live channel. `seq` mirrors the
    persisted AgentEvent.seq so a reconnecting client can de-duplicate
    against what it already replayed from the events endpoint.

    `workspace_id` scopes the transport channel and is never sent to the
    browser; everything in `public_dict` is safe, already-sanitized metadata.
    """

    run_public_id: str
    seq: int
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    workspace_id: int | None = None
    event_id: str | None = None
    trace_id: str | None = None

    def public_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "run_id": self.run_public_id,
            "seq": self.seq,
            "event_type": self.event_type,
            "payload": self.payload,
            "created_at": self.created_at.isoformat(),
            "trace_id": self.trace_id,
        }

    def as_sse(self) -> str:
        data = json.dumps(self.public_dict(), default=str)
        return f"id: {self.seq}\nevent: {self.event_type}\ndata: {data}\n\n"

    def to_wire(self) -> str:
        """Inter-worker encoding (Redis): the same safe fields plus the scope."""
        return json.dumps({**self.public_dict(), "workspace_id": self.workspace_id}, default=str)

    @classmethod
    def from_wire(cls, raw: str | bytes) -> LiveAgentEvent:
        data = json.loads(raw)
        workspace_id = data.get("workspace_id")
        return cls(
            run_public_id=str(data["run_id"]),
            seq=int(data["seq"]),
            event_type=str(data["event_type"]),
            payload=sanitize_payload(data.get("payload") or {}),
            created_at=datetime.fromisoformat(str(data["created_at"])),
            workspace_id=int(workspace_id) if workspace_id is not None else None,
            event_id=data.get("event_id"),
            trace_id=data.get("trace_id"),
        )


class BrokerUnavailableError(RuntimeError):
    """The live transport could not open a subscription. Callers degrade to
    persisted replay: events are never lost, only liveness."""


class EventBroker(Protocol):
    """The seam between event producers and live SSE subscribers."""

    name: str
    #: True only when a publish on one API worker reaches subscribers on another.
    multi_worker: bool

    def publish(self, event: LiveAgentEvent) -> None: ...

    def subscribe(
        self, run_public_id: str, workspace_id: int | None = None
    ) -> queue.Queue[LiveAgentEvent]: ...

    def unsubscribe(self, run_public_id: str, channel: queue.Queue[LiveAgentEvent]) -> None: ...

    def subscriber_count(self, run_public_id: str) -> int: ...

    def reset(self) -> None: ...


class InMemoryAgentEventBroker:
    """Minimal in-process pub/sub for live agent events.

    `publish` fans an event out to every currently-subscribed queue for that
    run; `subscribe` hands back a bounded queue.

    **In-process only**: correct for a single API worker (development, test,
    or a deployment that sets AGENT_EVENT_BROKER_SINGLE_WORKER=true).
    Multi-worker deployments use RedisAgentEventBroker behind the same
    surface. Persisted AgentEvent rows remain the source of truth in every
    topology.
    """

    name = "inmemory"
    multi_worker = False

    def __init__(self, max_queue_size: int = 512) -> None:
        self._max_queue_size = max_queue_size
        self._lock = threading.Lock()
        self._subscribers: dict[str, list[queue.Queue[LiveAgentEvent]]] = {}

    def publish(self, event: LiveAgentEvent) -> None:
        with self._lock:
            targets = list(self._subscribers.get(event.run_public_id, ()))
        for target in targets:
            try:
                target.put_nowait(event)
            except queue.Full:
                # A subscriber that cannot keep up must not slow the agent
                # loop down or block other subscribers. It falls back to
                # replaying persisted events on reconnect.
                continue

    def subscribe(
        self, run_public_id: str, workspace_id: int | None = None
    ) -> queue.Queue[LiveAgentEvent]:
        channel: queue.Queue[LiveAgentEvent] = queue.Queue(maxsize=self._max_queue_size)
        with self._lock:
            self._subscribers.setdefault(run_public_id, []).append(channel)
        return channel

    def unsubscribe(self, run_public_id: str, channel: queue.Queue[LiveAgentEvent]) -> None:
        with self._lock:
            channels = self._subscribers.get(run_public_id)
            if not channels:
                return
            try:
                channels.remove(channel)
            except ValueError:
                return
            if not channels:
                self._subscribers.pop(run_public_id, None)

    def subscriber_count(self, run_public_id: str) -> int:
        with self._lock:
            return len(self._subscribers.get(run_public_id, ()))

    @contextmanager
    def subscription(self, run_public_id: str) -> Iterator[queue.Queue[LiveAgentEvent]]:
        channel = self.subscribe(run_public_id)
        try:
            yield channel
        finally:
            self.unsubscribe(run_public_id, channel)

    def reset(self) -> None:
        """Test hook: drop every subscriber. Never called by request code."""
        with self._lock:
            self._subscribers.clear()


#: Backwards-compatible name for the in-process broker.
AgentEventBroker = InMemoryAgentEventBroker


@dataclass
class _RedisSubscription:
    pubsub: Any
    thread: threading.Thread
    stop: threading.Event


class RedisAgentEventBroker:
    """Cross-worker live events over Redis pub/sub.

    Channel: ``{prefix}:{workspace_id}:{run_public_id}``, scoped by BOTH
    tenant and run, so a subscriber can only ever hear its own run.

    Pub/sub is fire-and-forget: an event published while a client is
    between connections is not buffered by Redis. That is safe here because
    every event is committed to AgentEvent BEFORE publish and the stream
    endpoint replays from the database on (re)connect.

    Each subscription gets one reader thread that moves messages from Redis
    into a local bounded queue, so the SSE generator consumes exactly the
    same queue interface as with the in-memory broker.
    """

    name = "redis"
    multi_worker = True

    def __init__(
        self, client: Any, *, prefix: str = "prospectiq:agent", max_queue_size: int = 512
    ) -> None:
        self._client = client
        self._prefix = prefix
        self._max_queue_size = max_queue_size
        self._lock = threading.Lock()
        self._subscriptions: dict[int, _RedisSubscription] = {}
        self._counts: dict[str, int] = {}

    def channel_name(self, workspace_id: int | None, run_public_id: str) -> str:
        if workspace_id is None:
            raise ValueError("Redis agent events require a workspace scope.")
        return f"{self._prefix}:{int(workspace_id)}:{run_public_id}"

    def publish(self, event: LiveAgentEvent) -> None:
        self._client.publish(
            self.channel_name(event.workspace_id, event.run_public_id), event.to_wire()
        )

    def subscribe(
        self, run_public_id: str, workspace_id: int | None = None
    ) -> queue.Queue[LiveAgentEvent]:
        channel_name = self.channel_name(workspace_id, run_public_id)
        local: queue.Queue[LiveAgentEvent] = queue.Queue(maxsize=self._max_queue_size)
        try:
            pubsub = self._client.pubsub(ignore_subscribe_messages=True)
            pubsub.subscribe(channel_name)
        except Exception as exc:  # noqa: BLE001 - any transport error degrades to replay
            raise BrokerUnavailableError(str(exc)) from exc
        stop = threading.Event()

        def pump() -> None:
            while not stop.is_set():
                try:
                    message = pubsub.get_message(timeout=0.2)
                except Exception:  # noqa: BLE001 - connection lost; the client replays
                    return
                if not message or message.get("type") != "message":
                    continue
                try:
                    event = LiveAgentEvent.from_wire(message["data"])
                except (ValueError, KeyError, TypeError):
                    continue
                # Defence in depth: never deliver an event whose own scope
                # disagrees with the channel it arrived on.
                if event.run_public_id != run_public_id or event.workspace_id != workspace_id:
                    continue
                try:
                    local.put_nowait(event)
                except queue.Full:
                    continue

        thread = threading.Thread(target=pump, name=f"agent-sse-{run_public_id}", daemon=True)
        with self._lock:
            self._subscriptions[id(local)] = _RedisSubscription(pubsub, thread, stop)
            self._counts[run_public_id] = self._counts.get(run_public_id, 0) + 1
        thread.start()
        return local

    def unsubscribe(self, run_public_id: str, channel: queue.Queue[LiveAgentEvent]) -> None:
        with self._lock:
            subscription = self._subscriptions.pop(id(channel), None)
            if subscription is None:
                return
            remaining = self._counts.get(run_public_id, 1) - 1
            if remaining > 0:
                self._counts[run_public_id] = remaining
            else:
                self._counts.pop(run_public_id, None)
        self._close(subscription)

    def subscriber_count(self, run_public_id: str) -> int:
        with self._lock:
            return self._counts.get(run_public_id, 0)

    def ping(self) -> bool:
        return bool(self._client.ping())

    def reset(self) -> None:
        with self._lock:
            subscriptions = list(self._subscriptions.values())
            self._subscriptions.clear()
            self._counts.clear()
        for subscription in subscriptions:
            self._close(subscription)

    @staticmethod
    def _close(subscription: _RedisSubscription) -> None:
        subscription.stop.set()
        subscription.thread.join(timeout=2)
        try:
            subscription.pubsub.close()
        except Exception:  # noqa: BLE001 - best effort on teardown
            pass


_BROKER: EventBroker | None = None
_BROKER_LOCK = threading.Lock()


def build_event_broker(settings: Any) -> EventBroker:
    """Deterministic selection from AGENT_EVENT_BROKER. Never falls back
    silently: asking for Redis without a usable URL is an error."""
    if settings.agent_event_broker == "redis":
        url = (settings.redis_url or "").strip()
        if not url:
            raise ValueError("AGENT_EVENT_BROKER=redis requires REDIS_URL.")
        import redis

        client = redis.Redis.from_url(url, socket_timeout=5, health_check_interval=30)
        return RedisAgentEventBroker(client, prefix=settings.agent_event_channel_prefix)
    return InMemoryAgentEventBroker()


def get_event_broker() -> EventBroker:
    global _BROKER
    if _BROKER is None:
        with _BROKER_LOCK:
            if _BROKER is None:
                from app.core.config import get_settings

                _BROKER = build_event_broker(get_settings())
    return _BROKER


def set_event_broker(broker: EventBroker | None) -> None:
    """Install a broker (tests, app startup). None re-selects lazily."""
    global _BROKER
    with _BROKER_LOCK:
        _BROKER = broker


__all__ = [
    "ACTION_APPROVED",
    "ACTION_COMPLETED",
    "ACTION_EXECUTING",
    "ACTION_FAILED",
    "ACTION_PROPOSED",
    "ACTION_REJECTED",
    "AGENT_CANCELLED",
    "AGENT_COMPLETED",
    "AGENT_FAILED",
    "AGENT_RESUMED",
    "AGENT_STARTED",
    "ASSISTANT_DELTA",
    "BUDGET_EXHAUSTED",
    "HEARTBEAT",
    "KNOWLEDGE_SELECTED",
    "KNOWN_EVENT_TYPES",
    "MODEL_COMPLETED",
    "MODEL_STARTED",
    "RAG_SEARCH_COMPLETED",
    "RAG_SEARCH_STARTED",
    "STREAM_CLOSING_EVENT_TYPES",
    "TOOL_COMPLETED",
    "TOOL_FAILED",
    "TOOL_REQUESTED",
    "TOOL_STARTED",
    "WAITING_FOR_APPROVAL",
    "AgentEventBroker",
    "BrokerUnavailableError",
    "EventBroker",
    "FINAL_EVIDENCE_REF_DROPPED",
    "InMemoryAgentEventBroker",
    "RedisAgentEventBroker",
    "build_event_broker",
    "set_event_broker",
    "LiveAgentEvent",
    "get_event_broker",
    "sanitize_payload",
]
