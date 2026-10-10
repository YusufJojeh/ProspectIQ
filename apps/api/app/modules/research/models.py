from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.utils.identifiers import new_public_id


class ResearchRun(Base):
    """One completed research_lead call (planned or agentic), independent of
    whether it succeeded. Delta Intelligence diffs the ResearchFactSnapshot
    rows of the latest OK run against the one before it -- this row is what
    "latest" and "before it" are ordered by.
    """

    __tablename__ = "research_runs"
    __table_args__ = (Index("ix_research_runs_lead_created_at", "lead_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(24), unique=True, default=lambda: new_public_id("rrun")
    )
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    depth: Mapped[str] = mapped_column(String(16))
    mode: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(32))
    providers_used_json: Mapped[list[str]] = mapped_column(JSON(), default=list)
    evidence_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    research_coverage: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))


class ResearchFactSnapshot(Base):
    """An immutable, per-claim-type canonical value captured at the end of one
    ResearchRun -- never updated after insert. A new run always writes a new
    set of rows rather than mutating the previous run's; FactDiffEngine reads
    two runs' worth of these to compute what changed between them.
    """

    __tablename__ = "research_fact_snapshots"
    __table_args__ = (
        Index("ix_research_fact_snapshots_lead_claim", "lead_id", "claim_type"),
        Index("ix_research_fact_snapshots_run_id", "research_run_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    research_run_id: Mapped[int] = mapped_column(ForeignKey("research_runs.id"), index=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    claim_type: Mapped[str] = mapped_column(String(64))
    value: Mapped[str] = mapped_column(String(512))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    captured_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))


class ResearchChangeEvent(Base):
    """One meaningful, backend-decided change to a canonical fact between two
    research runs. `event_type`/`direction`/`significance` are all computed
    deterministically by FactDiffEngine -- an LLM is only ever used, after the
    fact, to fill in `explanation` with a human-readable sentence about why
    the change matters. It never decides whether a change occurred.
    """

    __tablename__ = "research_change_events"
    __table_args__ = (Index("ix_research_change_events_lead_created_at", "lead_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(24), unique=True, default=lambda: new_public_id("rce")
    )
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    previous_research_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("research_runs.id"), nullable=True
    )
    current_research_run_id: Mapped[int] = mapped_column(ForeignKey("research_runs.id"))
    claim_type: Mapped[str] = mapped_column(String(64))
    previous_value: Mapped[str | None] = mapped_column(String(512), nullable=True)
    new_value: Mapped[str | None] = mapped_column(String(512), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64))
    direction: Mapped[str] = mapped_column(String(16))
    significance: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[str | None] = mapped_column(Text(), nullable=True)
    triggered_rescore: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))


class ResearchContradiction(Base):
    """A claim where two or more providers disagree for the same lead.

    Populated by ContradictionDetector after a research run persists new
    ProviderNormalizedFact rows; `values_json` holds one entry per distinct
    value observed (value, provider, source_url, confidence).
    """

    __tablename__ = "research_contradictions"
    __table_args__ = (
        Index("ix_research_contradictions_lead_claim", "lead_id", "claim_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    claim_type: Mapped[str] = mapped_column(String(32))
    values_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON())
    detected_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))
