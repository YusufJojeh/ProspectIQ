from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.modules.scoring.models import (
    LeadScore,
    ScoreBreakdown,
    ScoringConfigVersion,
    WorkspaceScoringActive,
)
from app.modules.scoring.schemas import (
    LeadScoreResult,
    ScoreBreakdownItem,
    ScoringThresholds,
    ScoringWeights,
)
from app.modules.scoring.strategies import (
    DataConfidenceStrategy,
    LocalTrustStrategy,
    NewsPresenceStrategy,
    OpportunityStrategy,
    ReviewScoreStrategy,
    ScoringStrategy,
    SearchVisibilityStrategy,
    WebsitePresenceStrategy,
)
from app.shared.dto.lead_facts import NormalizedLeadFacts
from app.shared.enums.jobs import LeadScoreBand

if TYPE_CHECKING:
    from app.modules.icp.models import LeadIcpMatch
    from app.modules.signals.models import LeadSignal


class ScoringEngine:
    def __init__(self) -> None:
        self.strategies: list[ScoringStrategy] = [
            LocalTrustStrategy(),
            WebsitePresenceStrategy(),
            SearchVisibilityStrategy(),
            OpportunityStrategy(),
            DataConfidenceStrategy(),
            ReviewScoreStrategy(),
            NewsPresenceStrategy(),
        ]

    def evaluate(
        self,
        facts: NormalizedLeadFacts,
        *,
        weights: ScoringWeights,
        thresholds: ScoringThresholds,
        is_qualified_candidate: bool = True,
        icp_match: LeadIcpMatch | None = None,
        lead_signals: list[LeadSignal] | None = None,
    ) -> LeadScoreResult:
        legacy_breakdown = [
            strategy.score(facts, getattr(weights, strategy.key)) for strategy in self.strategies
        ]
        legacy_total_score = round(sum(item.contribution for item in legacy_breakdown), 2)
        qualified = bool(
            is_qualified_candidate and facts.data_confidence >= thresholds.confidence_min
        )
        if icp_match is None and not lead_signals:
            band = self._legacy_band(legacy_total_score, thresholds, qualified)
            return LeadScoreResult(
                total_score=legacy_total_score,
                band=band,
                qualified=qualified,
                breakdown=legacy_breakdown,
            )

        signal_map = {
            signal.signal_type: signal.signal_strength for signal in lead_signals or []
        }
        fit_score = self._fit_score(facts, icp_match)
        need_score = self._need_score(facts, signal_map)
        urgency_score = self._urgency_score(facts, signal_map)
        reachability_score = self._reachability_score(facts)
        final_priority_score = round(
            (fit_score * 0.35)
            + (need_score * 0.30)
            + (urgency_score * 0.20)
            + (reachability_score * 0.15),
            2,
        )
        qualified = bool(
            qualified
            and signal_map.get("low_rating", 0.0) < 0.9
            and fit_score >= 35.0
        )
        band = self._priority_band(
            final_priority_score=final_priority_score,
            fit_score=fit_score,
            qualified=qualified,
            signal_map=signal_map,
        )
        return LeadScoreResult(
            total_score=final_priority_score,
            fit_score=fit_score,
            need_score=need_score,
            urgency_score=urgency_score,
            reachability_score=reachability_score,
            final_priority_score=final_priority_score,
            band=band,
            qualified=qualified,
            breakdown=[
                ScoreBreakdownItem(
                    key="fit_score",
                    label="ICP Fit",
                    weight=0.35,
                    contribution=round(fit_score * 0.35, 2),
                    reason=(
                        "Best matching ICP profile fit score."
                        if icp_match is not None
                        else "No ICP profile matched yet; fit estimated from lead confidence and category clarity."
                    ),
                ),
                ScoreBreakdownItem(
                    key="need_score",
                    label="Need",
                    weight=0.30,
                    contribution=round(need_score * 0.30, 2),
                    reason="Need reflects website gaps, low rating, missing phone, and poor completeness signals.",
                ),
                ScoreBreakdownItem(
                    key="urgency_score",
                    label="Urgency",
                    weight=0.20,
                    contribution=round(urgency_score * 0.20, 2),
                    reason="Urgency reflects high reviews, local visibility, competitor gap, and outreach readiness.",
                ),
                ScoreBreakdownItem(
                    key="reachability_score",
                    label="Reachability",
                    weight=0.15,
                    contribution=round(reachability_score * 0.15, 2),
                    reason="Reachability is based on phone, website, and source confidence.",
                ),
                ScoreBreakdownItem(
                    key="legacy_evidence_score",
                    label="Legacy Evidence Score",
                    weight=0.0,
                    contribution=0.0,
                    reason=(
                        "Compatibility score from the original deterministic scoring "
                        f"strategies: {legacy_total_score}/100."
                    ),
                ),
            ],
        )

    def _legacy_band(
        self, total_score: float, thresholds: ScoringThresholds, qualified: bool
    ) -> LeadScoreBand:
        if not qualified:
            return LeadScoreBand.NOT_QUALIFIED
        if total_score >= thresholds.high_min:
            return LeadScoreBand.HIGH
        if total_score >= thresholds.medium_min:
            return LeadScoreBand.MEDIUM
        if total_score >= thresholds.low_min:
            return LeadScoreBand.LOW
        return LeadScoreBand.NOT_QUALIFIED

    def _priority_band(
        self,
        *,
        final_priority_score: float,
        fit_score: float,
        qualified: bool,
        signal_map: dict[str, float],
    ) -> LeadScoreBand:
        if (
            not qualified
            or fit_score < 35.0
            or signal_map.get("low_rating", 0.0) >= 0.9
            or signal_map.get("poor_data_completeness", 0.0) >= 0.8
        ):
            return LeadScoreBand.DO_NOT_CONTACT
        if final_priority_score >= 80:
            return LeadScoreBand.HOT_LEAD
        if final_priority_score >= 65:
            return LeadScoreBand.WARM_LEAD
        if final_priority_score >= 45:
            return LeadScoreBand.RESEARCH_MORE
        if final_priority_score >= 25:
            return LeadScoreBand.LOW_PRIORITY
        return LeadScoreBand.DO_NOT_CONTACT

    def _fit_score(self, facts: NormalizedLeadFacts, icp_match: LeadIcpMatch | None) -> float:
        if icp_match is not None:
            return round(max(0.0, min(100.0, icp_match.fit_score)), 2)
        return round(
            max(
                0.0,
                min(
                    100.0,
                    (facts.data_confidence * 45)
                    + (facts.category_clarity * 25)
                    + (facts.local_presence_signal * 20)
                    + (10 if facts.city else 0),
                ),
            ),
            2,
        )

    def _need_score(self, facts: NormalizedLeadFacts, signal_map: dict[str, float]) -> float:
        signal_need = max(
            signal_map.get("no_website", 0.0),
            signal_map.get("weak_website", 0.0),
            signal_map.get("poor_data_completeness", 0.0),
            signal_map.get("missing_phone", 0.0) * 0.6,
            signal_map.get("low_rating", 0.0) * 0.5,
        )
        footprint_need = max(facts.weak_website_signal, facts.digital_footprint_gap)
        return round(max(0.0, min(100.0, ((signal_need * 0.65) + (footprint_need * 0.35)) * 100)), 2)

    def _urgency_score(self, facts: NormalizedLeadFacts, signal_map: dict[str, float]) -> float:
        values = [
            signal_map.get("high_reviews", 0.0),
            signal_map.get("high_local_visibility", 0.0),
            signal_map.get("competitor_gap", 0.0),
            signal_map.get("ready_for_outreach", 0.0),
            facts.local_presence_signal,
        ]
        return round(max(0.0, min(100.0, (sum(values) / len(values)) * 100)), 2)

    def _reachability_score(self, facts: NormalizedLeadFacts) -> float:
        components = [
            1.0 if facts.phone_present else 0.0,
            1.0 if facts.email_present else 0.0,
            1.0 if facts.has_website else 0.0,
            facts.data_confidence,
            facts.source_agreement,
        ]
        return round(max(0.0, min(100.0, (sum(components) / len(components)) * 100)), 2)


class ScoringConfigService:
    def get_active_version(self, db: Session, workspace_id: int) -> ScoringConfigVersion:
        active = db.get(WorkspaceScoringActive, workspace_id)
        if active is None:
            raise NotFoundError("Active scoring configuration is not set.")
        version = db.get(ScoringConfigVersion, active.active_scoring_config_version_id)
        if version is None:
            raise NotFoundError("Active scoring configuration was not found.")
        return version

    def ensure_active_version(
        self, db: Session, workspace_id: int, *, created_by_user_id: int
    ) -> ScoringConfigVersion:
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

    def activate_version(
        self, db: Session, *, workspace_id: int, version: ScoringConfigVersion
    ) -> None:
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
        fit_score=result.fit_score,
        need_score=result.need_score,
        urgency_score=result.urgency_score,
        reachability_score=result.reachability_score,
        final_priority_score=result.final_priority_score,
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
