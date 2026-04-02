from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.modules.leads.schemas import LeadEvidenceItem, LeadScoreBreakdownResponse, ScoreBreakdownItem
from app.modules.provider_serpapi.models import ProviderNormalizedFact
from app.modules.scoring.models import LeadScore, ScoreBreakdown, ScoringConfigVersion
from app.shared.enums.jobs import LeadScoreBand


class ScoringRepository:
    def list_evidence_items(self, db: Session, lead_id: int) -> list[LeadEvidenceItem]:
        statement = (
            select(ProviderNormalizedFact)
            .where(ProviderNormalizedFact.lead_id == lead_id)
            .order_by(ProviderNormalizedFact.created_at.desc())
        )
        items = list(db.scalars(statement))
        return [
            LeadEvidenceItem(
                source_type=item.source_type,
                data_cid=item.data_cid,
                data_id=item.data_id,
                place_id=item.place_id,
                company_name=item.company_name,
                category=item.category,
                address=item.address,
                city=item.city,
                phone=item.phone,
                website_url=item.website_url,
                website_domain=item.website_domain,
                rating=item.rating,
                review_count=item.review_count,
                lat=item.lat,
                lng=item.lng,
                confidence=item.confidence,
                completeness=item.completeness,
                created_at=item.created_at,
            )
            for item in items
        ]

    def get_latest_score_breakdown(self, db: Session, lead_id: int) -> LeadScoreBreakdownResponse:
        score_stmt = (
            select(LeadScore)
            .where(LeadScore.lead_id == lead_id)
            .order_by(LeadScore.scored_at.desc())
            .limit(1)
        )
        score = db.scalar(score_stmt)
        if score is None:
            raise NotFoundError("Lead has not been scored yet.")

        breakdown_stmt = select(ScoreBreakdown).where(ScoreBreakdown.lead_score_id == score.id)
        breakdown = list(db.scalars(breakdown_stmt))

        version = db.scalar(select(ScoringConfigVersion).where(ScoringConfigVersion.id == score.scoring_config_version_id))
        version_public_id = version.public_id if version else "unknown"

        return LeadScoreBreakdownResponse(
            lead_id=str(lead_id),
            scoring_version_id=version_public_id,
            total_score=score.total_score,
            band=LeadScoreBand(score.band),
            qualified=score.qualified,
            breakdown=[
                ScoreBreakdownItem(
                    key=item.key,
                    label=item.label,
                    weight=item.weight,
                    contribution=item.contribution,
                    reason=item.reason,
                )
                for item in breakdown
            ],
        )
