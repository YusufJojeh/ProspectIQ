from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.utils.identifiers import new_public_id


class AgentRun(Base):
    """One user-initiated, model-directed agent conversation.

    A run holds durable state across a pause for human approval: the same
    row is re-entered by AgentRuntime.resume() rather than a new run being
    created, so `status` transitions through waiting_for_approval and back
    to running without losing the surrounding AgentMessage/AgentToolCall
    history. No chain-of-thought is ever persisted here or on AgentMessage --
    only tool-call metadata, tool results, and the final structured answer.
    """

    __tablename__ = "agent_runs"
    __table_args__ = (Index("ix_agent_runs_workspace_created_at", "workspace_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(24), unique=True, default=lambda: new_public_id("arun")
    )
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    lead_id: Mapped[int | None] = mapped_column(ForeignKey("leads.id"), index=True, nullable=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    goal: Mapped[str] = mapped_column(Text())
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    #: Which AgentProfile governed this run (allowed tools, risk ceiling,
    #: budgets, model routing). Recorded so a historical run stays
    #: interpretable after a profile's policy is changed.
    profile: Mapped[str] = mapped_column(String(32), default="research", index=True)
    provider: Mapped[str] = mapped_column(String(32), default="openai")
    model: Mapped[str] = mapped_column(String(64), default="")
    #: Versioned system prompt actually used, from the Prompt Registry.
    #: Historical runs keep pointing at the version they ran with, so
    #: activating a new prompt version never rewrites past behaviour.
    prompt_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Why the loop stopped short, when it did (a budget name, e.g.
    #: "max_steps"). Null for a run that finished on the model's own final
    #: answer.
    stop_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    step_count: Mapped[int] = mapped_column(Integer, default=0)
    tool_call_count: Mapped[int] = mapped_column(Integer, default=0)
    external_search_count: Mapped[int] = mapped_column(Integer, default=0)
    crawl_count: Mapped[int] = mapped_column(Integer, default=0)
    write_proposal_count: Mapped[int] = mapped_column(Integer, default=0)
    rag_query_count: Mapped[int] = mapped_column(Integer, default=0)
    model_call_count: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    embedding_tokens: Mapped[int] = mapped_column(Integer, default=0)
    #: Rolled-up cost for this run, in micro-USD (integer, so no float drift
    #: accumulates over many small provider calls). Derived from the
    #: ProviderUsage ledger, which stays the authoritative record.
    cost_micro_usd: Mapped[int] = mapped_column(Integer, default=0)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trace_id: Mapped[str] = mapped_column(String(64), default=lambda: new_public_id("trace"))
    final_answer_json: Mapped[dict[str, Any] | None] = mapped_column(JSON(), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), default=lambda: datetime.now(tz=UTC), onupdate=lambda: datetime.now(tz=UTC)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)


class AgentMessage(Base):
    """One turn of the conversation the model actually sees.

    Only `role in {system, user, assistant, tool}` content the provider API
    exchanged is stored -- never hidden chain-of-thought/reasoning tokens.
    `content` for an assistant turn that only requested tool calls is left
    null; the tool calls themselves are recorded as AgentToolCall rows.
    """

    __tablename__ = "agent_messages"
    __table_args__ = (Index("ix_agent_messages_run_seq", "agent_run_id", "seq"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    agent_run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str | None] = mapped_column(Text(), nullable=True)
    tool_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tool_call_public_id: Mapped[str | None] = mapped_column(String(24), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))


class AgentToolCall(Base):
    """One tool invocation the model requested, whether executed immediately
    (READ/RESEARCH/auto-approved WRITE_PROPOSAL) or turned into a pending
    AgentAction (WRITE_PROPOSAL requiring approval / ACTION). `result_json`
    is the bounded/truncated result the model actually saw -- never a raw,
    unbounded provider payload.
    """

    __tablename__ = "agent_tool_calls"
    __table_args__ = (
        Index("ix_agent_tool_calls_run_seq", "agent_run_id", "seq"),
        Index("ix_agent_tool_calls_run_hash", "agent_run_id", "arguments_hash"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(24), unique=True, default=lambda: new_public_id("atc")
    )
    agent_run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    tool_name: Mapped[str] = mapped_column(String(64))
    tool_type: Mapped[str] = mapped_column(String(24))
    arguments_json: Mapped[dict[str, Any]] = mapped_column(JSON(), default=dict)
    arguments_hash: Mapped[str] = mapped_column(String(64), index=True)
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON(), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="pending")
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))


class AgentAction(Base):
    """A proposed domain mutation awaiting (or having received) human
    approval. Created with an exact, human-readable `preview_json` and the
    literal `payload_json` the domain service will be called with --
    proposing an action must never itself mutate business data. `status`
    transitions are claimed atomically by AgentActionGate via a
    conditional UPDATE ... WHERE status = 'pending', so concurrent/duplicate
    approve calls can execute the underlying domain service at most once.
    """

    __tablename__ = "agent_actions"
    __table_args__ = (
        Index("ix_agent_actions_workspace_status", "workspace_id", "status"),
        Index("ix_agent_actions_run_id", "agent_run_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(24), unique=True, default=lambda: new_public_id("aact")
    )
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    agent_run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    tool_call_id: Mapped[int | None] = mapped_column(
        ForeignKey("agent_tool_calls.id"), nullable=True
    )
    tool_name: Mapped[str] = mapped_column(String(64))
    resource_type: Mapped[str] = mapped_column(String(32))
    resource_id: Mapped[str] = mapped_column(String(64))
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON(), default=dict)
    payload_hash: Mapped[str] = mapped_column(String(64))
    preview_json: Mapped[dict[str, Any]] = mapped_column(JSON(), default=dict)
    risk_level: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON(), nullable=True)
    approved_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime())
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True)
    trace_id: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), default=lambda: datetime.now(tz=UTC), onupdate=lambda: datetime.now(tz=UTC)
    )


class AgentEvent(Base):
    """One persisted lifecycle event, in strict per-run order, replayed by
    GET /agent/runs/{run_id}/events. `payload_json` is bounded, structured
    data (tool name, action id, status) -- never chain-of-thought text.
    """

    __tablename__ = "agent_events"
    __table_args__ = (Index("ix_agent_events_run_seq", "agent_run_id", "seq"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(24), unique=True, default=lambda: new_public_id("aev")
    )
    agent_run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(32))
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON(), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))


__all__ = [
    "AgentAction",
    "AgentEvent",
    "AgentMessage",
    "AgentRun",
    "AgentToolCall",
]
