from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.modules.leads.models import Lead
from app.modules.provider_serpapi.repository import ProviderEvidenceRepository
from app.modules.scoring.fact_builder import EvidenceFactBuilder
from app.modules.scoring.repository import ScoringRepository
from app.shared.dto.lead_facts import NormalizedLeadFacts
from app.shared.dto.lead_score_context import LeadScoreContext


@dataclass(slots=True)
class LeadIntelligenceContext:
    facts: NormalizedLeadFacts
    score_context: LeadScoreContext | None


class LeadIntelligenceService:
    def __init__(self) -> None:
        self.evidence_repository = ProviderEvidenceRepository()
        self.fact_builder = EvidenceFactBuilder()
        self.scoring_repository = ScoringRepository()

    def build(self, db: Session, *, lead: Lead) -> LeadIntelligenceContext:
        facts = self.build_facts(db, lead=lead)
        score_context = self.build_score_context(db, lead_id=lead.id)
        return LeadIntelligenceContext(facts=facts, score_context=score_context)

    def build_facts(self, db: Session, *, lead: Lead) -> NormalizedLeadFacts:
        evidence = self.evidence_repository.list_normalized_facts_for_lead(db, lead.id)
        return self.fact_builder.build(lead, evidence)

    def build_score_context(self, db: Session, *, lead_id: int) -> LeadScoreContext | None:
        try:
            breakdown = self.scoring_repository.get_latest_score_breakdown(db, lead_id)
        except NotFoundError:
            return None

        reasons = [
            item.reason
            for item in sorted(
                breakdown.breakdown,
                key=lambda item: abs(item.contribution),
                reverse=True,
            )[:3]
        ]
        return LeadScoreContext(
            total_score=breakdown.total_score,
            band=breakdown.band.value,
            qualified=breakdown.qualified,
            reasons=reasons,
        )
