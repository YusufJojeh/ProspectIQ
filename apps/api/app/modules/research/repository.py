from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.research.models import (
    ResearchChangeEvent,
    ResearchContradiction,
    ResearchFactSnapshot,
    ResearchRun,
)
from app.modules.research.schemas import ContradictionSummary
from app.shared.enums.jobs import ProviderFetchStatus

# ResearchFactSnapshot.value is String(512); values from providers (URLs,
# addresses) can occasionally run longer, so truncate defensively rather than
# let an outlier fail the whole research run.
_MAX_SNAPSHOT_VALUE_LENGTH = 512


class ResearchRepository:
    def list_history(
        self,
        db: Session,
        *,
        workspace_id: int,
        lead_id: int,
        page: int,
        per_page: int,
    ) -> tuple[list[ResearchRun], int, dict[int, list[ResearchChangeEvent]]]:
        filters = (
            ResearchRun.workspace_id == workspace_id,
            ResearchRun.lead_id == lead_id,
        )
        total = int(db.scalar(select(func.count(ResearchRun.id)).where(*filters)) or 0)
        statement = (
            select(ResearchRun)
            .where(*filters)
            .order_by(ResearchRun.created_at.desc(), ResearchRun.id.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        runs = list(db.scalars(statement))
        run_ids = [run.id for run in runs]
        changes_by_run: dict[int, list[ResearchChangeEvent]] = {run_id: [] for run_id in run_ids}
        if run_ids:
            changes = db.scalars(
                select(ResearchChangeEvent)
                .where(
                    ResearchChangeEvent.workspace_id == workspace_id,
                    ResearchChangeEvent.lead_id == lead_id,
                    ResearchChangeEvent.current_research_run_id.in_(run_ids),
                )
                .order_by(ResearchChangeEvent.created_at.asc(), ResearchChangeEvent.id.asc())
            )
            for change in changes:
                changes_by_run[change.current_research_run_id].append(change)
        return runs, total, changes_by_run

    def save_contradictions(
        self,
        db: Session,
        *,
        workspace_id: int,
        lead_id: int,
        contradictions: list[ContradictionSummary],
    ) -> None:
        if not contradictions:
            return
        for item in contradictions:
            db.add(
                ResearchContradiction(
                    workspace_id=workspace_id,
                    lead_id=lead_id,
                    claim_type=item.claim_type,
                    values_json=[value.model_dump() for value in item.values],
                )
            )
        db.commit()

    def get_latest_ok_run(self, db: Session, lead_id: int) -> ResearchRun | None:
        statement = (
            select(ResearchRun)
            .where(ResearchRun.lead_id == lead_id, ResearchRun.status == ProviderFetchStatus.OK.value)
            .order_by(ResearchRun.created_at.desc(), ResearchRun.id.desc())
            .limit(1)
        )
        return db.scalar(statement)

    def load_snapshot_map(self, db: Session, research_run_id: int) -> dict[str, tuple[str, float]]:
        statement = select(ResearchFactSnapshot).where(
            ResearchFactSnapshot.research_run_id == research_run_id
        )
        return {row.claim_type: (row.value, row.confidence) for row in db.scalars(statement)}

    def create_run(
        self,
        db: Session,
        *,
        workspace_id: int,
        lead_id: int,
        depth: str,
        mode: str,
        status: str,
        providers_used: list[str],
        evidence_confidence: float,
        research_coverage: float,
    ) -> ResearchRun:
        run = ResearchRun(
            workspace_id=workspace_id,
            lead_id=lead_id,
            depth=depth,
            mode=mode,
            status=status,
            providers_used_json=providers_used,
            evidence_confidence=evidence_confidence,
            research_coverage=research_coverage,
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    def save_snapshot(
        self,
        db: Session,
        *,
        research_run_id: int,
        workspace_id: int,
        lead_id: int,
        snapshot_map: dict[str, tuple[str, float]],
    ) -> None:
        if not snapshot_map:
            return
        for claim_type, (value, confidence) in snapshot_map.items():
            db.add(
                ResearchFactSnapshot(
                    research_run_id=research_run_id,
                    workspace_id=workspace_id,
                    lead_id=lead_id,
                    claim_type=claim_type,
                    value=value[:_MAX_SNAPSHOT_VALUE_LENGTH],
                    confidence=confidence,
                )
            )
        db.commit()

    def save_change_event(
        self,
        db: Session,
        *,
        workspace_id: int,
        lead_id: int,
        previous_research_run_id: int | None,
        current_research_run_id: int,
        claim_type: str,
        previous_value: str | None,
        new_value: str | None,
        event_type: str,
        direction: str,
        significance: float,
        explanation: str | None,
        triggered_rescore: bool,
    ) -> ResearchChangeEvent:
        event = ResearchChangeEvent(
            workspace_id=workspace_id,
            lead_id=lead_id,
            previous_research_run_id=previous_research_run_id,
            current_research_run_id=current_research_run_id,
            claim_type=claim_type,
            previous_value=(previous_value or "")[:_MAX_SNAPSHOT_VALUE_LENGTH] or None,
            new_value=(new_value or "")[:_MAX_SNAPSHOT_VALUE_LENGTH] or None,
            event_type=event_type,
            direction=direction,
            significance=significance,
            explanation=explanation,
            triggered_rescore=triggered_rescore,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event
