from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.modules.scoring.models import LeadScore, ScoreBreakdown, ScoringConfigVersion, WorkspaceScoringActive
from app.modules.scoring.schemas import LeadScoreResult, ScoringThresholds, ScoringWeights
from app.modules.scoring.strategies import (
    DataConfidenceStrategy,
    LocalTrustStrategy,
    OpportunityStrategy,
    SearchVisibilityStrategy,
    WebsitePresenceStrategy,
)
from app.shared.dto.lead_facts import NormalizedLeadFacts
from app.shared.enums.jobs import LeadScoreBand


class ScoringEngine:
    def __init__(self) -> None:
        self.strategies = [
            LocalTrustStrategy(),
            WebsitePresenceStrategy(),
            SearchVisibilityStrategy(),
            OpportunityStrategy(),
            DataConfidenceStrategy(),
        ]

    def evaluate(
        self,
        facts: NormalizedLeadFacts,
        *,
        weights: ScoringWeights,
        thresholds: ScoringThresholds,
        is_qualified_candidate: bool = True,
    ) -> LeadScoreResult:
        breakdown = [strategy.score(facts, getattr(weights, strategy.key)) for strategy in self.strategies]
        total_score = round(sum(item.contribution for item in breakdown), 2)
        qualified = bool(is_qualified_candidate and facts.data_confidence >= thresholds.confidence_min)
        band = self._band(total_score, thresholds, qualified)
        return LeadScoreResult(total_score=total_score, band=band, qualified=qualified, breakdown=breakdown)

    def _band(self, total_score: float, thresholds: ScoringThresholds, qualified: bool) -> LeadScoreBand:
        if not qualified:
            return LeadScoreBand.NOT_QUALIFIED
        if total_score >= thresholds.high_min:
            return LeadScoreBand.HIGH
        if total_score >= thresholds.medium_min:
            return LeadScoreBand.MEDIUM
        if total_score >= thresholds.low_min:
            return LeadScoreBand.LOW
        return LeadScoreBand.NOT_QUALIFIED


class ScoringConfigService:
    def get_active_version(self, db: Session, workspace_id: int) -> ScoringConfigVersion:
        active = db.get(WorkspaceScoringActive, workspace_id)
        if active is None:
            raise NotFoundError("Active scoring configuration is not set.")
        version = db.get(ScoringConfigVersion, active.active_scoring_config_version_id)
        if version is None:
            raise NotFoundError("Active scoring configuration was not found.")
        return version

    def ensure_active_version(self, db: Session, workspace_id: int, *, created_by_user_id: int) -> ScoringConfigVersion:
        active = db.get(WorkspaceScoringActive, workspace_id)
        if active is not None:
            version = db.get(ScoringConfigVersion, active.active_scoring_config_version_id)
            if version is not None:
                return version

        default = ScoringConfigVersion(
            workspace_id=workspace_id,
            created_by_user_id=created_by_user_id,
            weights_json=ScoringWeights().model_dump(),
            thresholds_json=ScoringThresholds().model_dump(),
            note="Auto-created default scoring config",
        )
        db.add(default)
        db.commit()
        db.refresh(default)
        db.add(
            WorkspaceScoringActive(
                workspace_id=workspace_id,
                active_scoring_config_version_id=default.id,
            )
        )
        db.commit()
        return default

    def create_version(
        self,
        db: Session,
        *,
        workspace_id: int,
        created_by_user_id: int,
        weights: ScoringWeights,
        thresholds: ScoringThresholds,
        note: str | None,
    ) -> ScoringConfigVersion:
        version = ScoringConfigVersion(
            workspace_id=workspace_id,
            created_by_user_id=created_by_user_id,
            weights_json=weights.model_dump(),
            thresholds_json=thresholds.model_dump(),
            note=note,
        )
        db.add(version)
        db.commit()
        db.refresh(version)
        return version

    def activate_version(self, db: Session, *, workspace_id: int, version: ScoringConfigVersion) -> None:
        if version.workspace_id != workspace_id:
            raise NotFoundError("Scoring configuration was not found.")
        active = db.get(WorkspaceScoringActive, workspace_id)
        if active is None:
            active = WorkspaceScoringActive(
                workspace_id=workspace_id,
                active_scoring_config_version_id=version.id,
            )
            db.add(active)
        else:
            active.active_scoring_config_version_id = version.id
        db.commit()


def persist_lead_score(
    db: Session,
    *,
    lead_id: int,
    scoring_config_version_id: int,
    result: LeadScoreResult,
) -> LeadScore:
    lead_score = LeadScore(
        lead_id=lead_id,
        scoring_config_version_id=scoring_config_version_id,
        total_score=result.total_score,
        band=result.band.value,
        qualified=result.qualified,
    )
    db.add(lead_score)
    db.commit()
    db.refresh(lead_score)
    breakdown = [
        ScoreBreakdown(
            lead_score_id=lead_score.id,
            key=item.key,
            label=item.label,
            weight=item.weight,
            contribution=item.contribution,
            reason=item.reason,
        )
        for item in result.breakdown
    ]
    db.add_all(breakdown)
    db.commit()
    return lead_score

