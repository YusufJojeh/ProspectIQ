from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.modules.ai_runtime.models import ProviderUsage
from app.modules.ai_runtime.pricing import PricingTable, get_pricing_table

# --- Usage ledger ---------------------------------------------------------
#
# One place records what the AI layer spent. Everything else -- agent runs,
# research runs, RAG ingestion, retrieval -- calls `record`, so adding a new
# provider caller never means inventing another set of counter columns.
#
# Costing happens here, at write time, from the pricing table in force now.
# A row therefore keeps the figure it was costed with: re-pricing history
# when a provider changes its rates would make the ledger disagree with the
# invoice it is supposed to reconcile against.

OPERATION_AGENT_RUN = "agent_run"
OPERATION_RESEARCH_RUN = "research_run"
OPERATION_EMBEDDING = "embedding"
OPERATION_EXTERNAL_SEARCH = "external_search"
OPERATION_CRAWL = "crawl"


@dataclass(frozen=True, slots=True)
class UsageTotals:
    input_tokens: int = 0
    output_tokens: int = 0
    embedding_tokens: int = 0
    units: int = 0
    #: None when ANY contributing row was unpriced -- see `cost_complete`.
    cost_micro_usd: int | None = None
    #: False when at least one row had no configured rate, so the total is a
    #: lower bound rather than the full spend. A budget must treat an
    #: incomplete total as "at least this much", never as the final figure.
    cost_complete: bool = True
    call_count: int = 0


@dataclass
class UsageLedger:
    pricing: PricingTable = field(default_factory=get_pricing_table)

    def record(
        self,
        db: Session,
        *,
        workspace_id: int,
        trace_id: str,
        operation: str,
        provider: str,
        model: str = "",
        subject_id: str | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        embedding_tokens: int = 0,
        units: int = 0,
        latency_ms: int = 0,
        status: str = "ok",
        fallback_from: str | None = None,
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProviderUsage:
        cost = self._cost(
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            embedding_tokens=embedding_tokens,
            units=units,
        )
        row = ProviderUsage(
            workspace_id=workspace_id,
            trace_id=trace_id,
            operation=operation,
            subject_id=subject_id,
            provider=provider,
            model=model,
            input_tokens=max(0, input_tokens),
            output_tokens=max(0, output_tokens),
            embedding_tokens=max(0, embedding_tokens),
            units=max(0, units),
            cost_micro_usd=cost,
            latency_ms=max(0, latency_ms),
            status=status,
            fallback_from=fallback_from,
            error_message=error_message,
            metadata_json=metadata,
        )
        db.add(row)
        db.flush()
        return row

    def _cost(
        self,
        *,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        embedding_tokens: int,
        units: int,
    ) -> int | None:
        # A component only counts when it was actually consumed. The
        # important case is a token call on a model with no configured rate:
        # its cost is UNKNOWN, and must not come out as 0 just because the
        # unit component happened to be zero.
        has_tokens = (input_tokens + output_tokens + embedding_tokens) > 0
        has_units = units > 0
        if not has_tokens and not has_units:
            return 0

        total = 0
        if has_tokens:
            token_cost = self.pricing.token_cost_micro_usd(
                provider=provider,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                embedding_tokens=embedding_tokens,
            )
            if token_cost is None:
                return None
            total += token_cost
        if has_units:
            unit_cost = self.pricing.unit_cost_micro_usd(
                provider=provider, model=model, units=units
            )
            if unit_cost is None:
                return None
            total += unit_cost
        return total

    def totals_for_trace(self, db: Session, *, trace_id: str) -> UsageTotals:
        return self._totals(db, ProviderUsage.trace_id == trace_id)

    def totals_for_subject(self, db: Session, *, subject_id: str) -> UsageTotals:
        return self._totals(db, ProviderUsage.subject_id == subject_id)

    def _totals(self, db: Session, condition: Any) -> UsageTotals:
        row = db.execute(
            select(
                func.coalesce(func.sum(ProviderUsage.input_tokens), 0),
                func.coalesce(func.sum(ProviderUsage.output_tokens), 0),
                func.coalesce(func.sum(ProviderUsage.embedding_tokens), 0),
                func.coalesce(func.sum(ProviderUsage.units), 0),
                func.coalesce(func.sum(ProviderUsage.cost_micro_usd), 0),
                func.count(ProviderUsage.id),
                func.coalesce(
                    func.sum(case((ProviderUsage.cost_micro_usd.is_(None), 1), else_=0)), 0
                ),
            ).where(condition)
        ).one()
        unpriced = int(row[6] or 0)
        return UsageTotals(
            input_tokens=int(row[0]),
            output_tokens=int(row[1]),
            embedding_tokens=int(row[2]),
            units=int(row[3]),
            cost_micro_usd=int(row[4]),
            cost_complete=unpriced == 0,
            call_count=int(row[5]),
        )


__all__ = [
    "OPERATION_AGENT_RUN",
    "OPERATION_CRAWL",
    "OPERATION_EMBEDDING",
    "OPERATION_EXTERNAL_SEARCH",
    "OPERATION_RESEARCH_RUN",
    "UsageLedger",
    "UsageTotals",
]
