from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.modules.leads.schemas import (
    LeadEvidenceItem,
    LeadScoreBreakdownResponse,
    ScoreBreakdownItem,
)
from app.modules.provider_serpapi.models import ProviderFetch, ProviderNormalizedFact
from app.modules.scoring.models import LeadScore, ScoreBreakdown, ScoringConfigVersion
from app.shared.enums.jobs import LeadScoreBand


class ScoringRepository:
    def list_evidence_items(self, db: Session, lead_id: int) -> list[LeadEvidenceItem]:
        statement = (
            select(ProviderNormalizedFact, ProviderFetch)
            .join(ProviderFetch, ProviderFetch.id == ProviderNormalizedFact.provider_fetch_id)
            .where(ProviderNormalizedFact.lead_id == lead_id)
            .order_by(ProviderNormalizedFact.created_at.desc(), ProviderNormalizedFact.id.desc())
        )
        rows = db.execute(statement).all()
        seen_keys: set[tuple[str, str, str, str, str, str, str]] = set()
        unique_rows: list[tuple[ProviderNormalizedFact, ProviderFetch]] = []
        for fact, fetch in rows:
            key = self._evidence_identity_key(fact)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            unique_rows.append((fact, fetch))

        return [
            LeadEvidenceItem(
                source_type=fact.source_type,
                provider_fetch_public_id=fetch.public_id,
                provider_status=fetch.status,
                request_mode=fetch.mode,
                http_status=fetch.http_status,
                data_cid=fact.data_cid,
                data_id=fact.data_id,
                place_id=fact.place_id,
                company_name=fact.company_name,
                category=fact.category,
                address=fact.address,
                city=fact.city,
                phone=fact.phone,
                website_url=fact.website_url,
                website_domain=fact.website_domain,
                rating=fact.rating,
                review_count=fact.review_count,
                lat=fact.lat,
                lng=fact.lng,
                confidence=fact.confidence,
                completeness=fact.completeness,
                facts=fact.facts_json,
                created_at=fact.created_at,
            )
            for fact, fetch in unique_rows
        ]

    def _evidence_identity_key(
        self,
        fact: ProviderNormalizedFact,
    ) -> tuple[str, str, str, str, str, str, str]:
        coordinates = ""
        if fact.lat is not None and fact.lng is not None:
            coordinates = f"{fact.lat:.6f},{fact.lng:.6f}"

        return (
            fact.source_type,
            (fact.place_id or "").strip().lower(),
            (fact.data_cid or "").strip().lower(),
            (fact.data_id or "").strip().lower(),
            (fact.website_domain or fact.website_url or "").strip().lower(),
            (fact.phone or "").strip().lower(),
            coordinates,
        )

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

        version = db.scalar(
            select(ScoringConfigVersion).where(
                ScoringConfigVersion.id == score.scoring_config_version_id
            )
        )
        version_public_id = version.public_id if version else "unknown"

        return LeadScoreBreakdownResponse(
            lead_id=str(lead_id),
            scoring_version_id=version_public_id,
            total_score=score.total_score,
            fit_score=score.fit_score,
            need_score=score.need_score,
            urgency_score=score.urgency_score,
            reachability_score=score.reachability_score,
            final_priority_score=score.final_priority_score,
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
