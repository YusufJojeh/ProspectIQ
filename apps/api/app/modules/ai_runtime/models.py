from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.utils.identifiers import new_public_id


class ProviderUsage(Base):
    """One billable provider interaction: a model call, an embedding batch,
    an external search or crawl.

    This is the single usage ledger for the whole AI layer. Rolled-up
    counters on AgentRun and ResearchRun are convenience views over these
    rows, not the source of truth -- a counter can be double-incremented by
    a retry, but a ledger row is written once per interaction and can be
    reconciled against a provider invoice line by line.
    """

    __tablename__ = "provider_usage"
    __table_args__ = (
        Index("ix_provider_usage_workspace_created", "workspace_id", "created_at"),
        Index("ix_provider_usage_trace", "trace_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(24), unique=True, default=lambda: new_public_id("use")
    )
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    #: The one identifier that ties a user request to every provider call it
    #: caused, across agent runs, research runs and RAG retrieval.
    trace_id: Mapped[str] = mapped_column(String(64), index=True)
    #: What kind of work this served: agent_run, research_run, ingestion,
    #: retrieval. Free-form on purpose so a new caller can record usage
    #: without a migration.
    operation: Mapped[str] = mapped_column(String(32), index=True)
    #: Public id of the owning run, when there is one.
    subject_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(32), index=True)
    model: Mapped[str] = mapped_column(String(64), default="")
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    embedding_tokens: Mapped[int] = mapped_column(Integer, default=0)
    #: Non-token-priced units: searches, actor runs, crawls.
    units: Mapped[int] = mapped_column(Integer, default=0)
    #: NULL means the cost is genuinely unknown (no configured rate for this
    #: provider/model). It is never coerced to 0, because "free" and "not
    #: priced" must not look alike in a spend report.
    cost_micro_usd: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="ok", index=True)
    #: Set when this call ran on a fallback provider/model: the name of the
    #: model originally routed to. Fallback is a behaviour change, so it is
    #: recorded rather than inferred.
    fallback_from: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))


class PromptVersion(Base):
    """A versioned system/instruction prompt.

    Prompts are behaviour. Changing one silently changes what every future
    run does, and leaves no way to explain why last week's run answered
    differently. AgentRun records the (prompt_key, version) it ran under, so
    activating a new version never rewrites the history of old runs.
    """

    __tablename__ = "prompt_versions"
    __table_args__ = (
        Index("ix_prompt_versions_key_version", "prompt_key", "version", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(24), unique=True, default=lambda: new_public_id("prm")
    )
    prompt_key: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    #: draft | active | retired. Exactly one active version per key is
    #: enforced by PromptRegistry.activate, in a transaction.
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    content: Mapped[str] = mapped_column(Text())
    checksum: Mapped[str] = mapped_column(String(64), default="")
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    #: Prompts are platform-level, not tenant data; a workspace cannot edit
    #: the instructions the runtime enforces itself with.
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=True)


__all__ = ["PromptVersion", "ProviderUsage"]
