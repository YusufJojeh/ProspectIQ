from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.modules.signals.models import LeadSignal, LeadSignalScore


@dataclass(frozen=True, slots=True)
class LeadSignalSummary:
    top_signal_type: str
    top_signal_strength: float
    top_signal_evidence: str
    signals_count: int


class LeadSignalRepository:
    def list_for_lead(
        self, db: Session, *, workspace_id: int, lead_id: int
    ) -> list[LeadSignal]:
        return list(
            db.scalars(
                select(LeadSignal)
                .where(
                    LeadSignal.workspace_id == workspace_id,
                    LeadSignal.lead_id == lead_id,
                )
                .order_by(LeadSignal.signal_strength.desc(), LeadSignal.detected_at.desc())
            )
        )

    def list_scores_for_lead(
        self, db: Session, *, workspace_id: int, lead_id: int
    ) -> list[LeadSignalScore]:
        return list(
            db.scalars(
                select(LeadSignalScore)
                .where(
                    LeadSignalScore.workspace_id == workspace_id,
                    LeadSignalScore.lead_id == lead_id,
                )
                .order_by(LeadSignalScore.score.desc(), LeadSignalScore.signal_type.asc())
            )
        )

    def summaries_for_leads(
        self, db: Session, *, workspace_id: int, lead_ids: list[int]
    ) -> dict[int, LeadSignalSummary]:
        """Bulk-load the top signal plus a count per lead in two scoped queries.

        Strictly workspace-scoped to avoid cross-tenant leakage and intentionally
        free of per-lead (N+1) round-trips for use in the lead list response.
        """
        if not lead_ids:
            return {}

        counts: dict[int, int] = {
            int(lead_id): int(count)
            for lead_id, count in db.execute(
                select(LeadSignal.lead_id, func.count(LeadSignal.id))
                .where(
                    LeadSignal.workspace_id == workspace_id,
                    LeadSignal.lead_id.in_(lead_ids),
                )
                .group_by(LeadSignal.lead_id)
            ).all()
        }
        if not counts:
            return {}

        # Strongest, most recent signal first; reduce to the first row per lead.
        rows = db.scalars(
            select(LeadSignal)
            .where(
                LeadSignal.workspace_id == workspace_id,
                LeadSignal.lead_id.in_(lead_ids),
            )
            .order_by(
                LeadSignal.lead_id.asc(),
                LeadSignal.signal_strength.desc(),
                LeadSignal.detected_at.desc(),
                LeadSignal.id.desc(),
            )
        )
        summaries: dict[int, LeadSignalSummary] = {}
        for signal in rows:
            if signal.lead_id in summaries:
                continue
            summaries[signal.lead_id] = LeadSignalSummary(
                top_signal_type=signal.signal_type,
                top_signal_strength=signal.signal_strength,
                top_signal_evidence=signal.evidence_text,
                signals_count=counts.get(signal.lead_id, 0),
            )
        return summaries

    def replace_for_lead(
        self,
        db: Session,
        *,
        workspace_id: int,
        lead_id: int,
        signals: list[LeadSignal],
        scores: list[LeadSignalScore],
    ) -> list[LeadSignal]:
        db.execute(
            delete(LeadSignal).where(
                LeadSignal.workspace_id == workspace_id,
                LeadSignal.lead_id == lead_id,
            )
        )
        db.execute(
            delete(LeadSignalScore).where(
                LeadSignalScore.workspace_id == workspace_id,
                LeadSignalScore.lead_id == lead_id,
            )
        )
        db.add_all([*signals, *scores])
        db.commit()
        for signal in signals:
            db.refresh(signal)
        return signals
