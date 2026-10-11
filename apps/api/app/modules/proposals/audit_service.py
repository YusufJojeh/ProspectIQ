from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.modules.auth.permissions import assert_workspace_permission
from app.modules.leads.models import Lead
from app.modules.leads.repository import LeadsRepository
from app.modules.proposals.audit import LeadFacts, PeerFacts, benchmark, build_findings
from app.modules.proposals.schemas import (
    AuditBenchmark,
    AuditEvidence,
    AuditFinding,
    LeadAuditResponse,
)
from app.modules.signals.models import LeadSignal
from app.modules.users.models import User

#: Enough similar businesses for a stable median without scanning a workspace.
_MAX_PEERS = 500
_MAX_EVIDENCE = 4


class LeadAuditService:
    """Builds the presence audit a salesperson sends a prospect: what the
    business looks like online, from facts already collected, next to the
    businesses found alongside it. Read-only; nothing is stored."""

    def __init__(self) -> None:
        self.leads_repository = LeadsRepository()

    def build(
        self, db: Session, *, workspace_id: int, lead_public_id: str, current_user: User
    ) -> LeadAuditResponse:
        assert_workspace_permission(
            current_user.role, "leads:view", message="You cannot view this lead."
        )
        lead = self.leads_repository.get_by_public_id_for_workspace(
            db, workspace_id=workspace_id, public_id=lead_public_id
        )
        if lead is None:
            raise NotFoundError("Lead was not found.")

        bench = benchmark(self._peers(db, lead))
        facts = LeadFacts(
            has_website=bool(lead.has_website or lead.website_url),
            rating=lead.rating,
            review_count=lead.review_count or 0,
            has_phone=bool(lead.phone and lead.phone.strip()),
            has_email=bool(lead.email and lead.email.strip()),
            has_social=bool(lead.linkedin_url and lead.linkedin_url.strip()),
        )
        return LeadAuditResponse(
            lead_id=lead.public_id,
            company_name=lead.company_name,
            category=lead.category,
            city=lead.city,
            website_url=lead.website_url,
            email=lead.email,
            generated_on=datetime.now(tz=UTC).date(),
            findings=[
                AuditFinding.model_validate(
                    {"key": item.key, "status": item.status, "values": item.values}
                )
                for item in build_findings(facts, bench)
            ],
            benchmark=(
                AuditBenchmark(
                    peer_count=bench.peer_count,
                    median_rating=bench.median_rating,
                    median_reviews=bench.median_reviews,
                    website_pct=bench.website_pct,
                )
                if bench is not None
                else None
            ),
            evidence=self._evidence(db, lead),
        )

    @staticmethod
    def _peers(db: Session, lead: Lead) -> list[PeerFacts]:
        """Businesses from the same search, or failing that the same category
        in the same city -- always inside the lead's own workspace."""
        query = select(Lead.rating, Lead.review_count, Lead.has_website, Lead.website_url).where(
            Lead.workspace_id == lead.workspace_id, Lead.id != lead.id
        )
        if lead.search_job_id is not None:
            query = query.where(Lead.search_job_id == lead.search_job_id)
        elif lead.category and lead.city:
            query = query.where(
                func.lower(Lead.category) == lead.category.lower(),
                func.lower(Lead.city) == lead.city.lower(),
            )
        else:
            return []
        rows = db.execute(query.order_by(Lead.id).limit(_MAX_PEERS)).all()
        return [
            PeerFacts(
                rating=rating,
                review_count=review_count or 0,
                has_website=bool(has_website or website_url),
            )
            for rating, review_count, has_website, website_url in rows
        ]

    @staticmethod
    def _evidence(db: Session, lead: Lead) -> list[AuditEvidence]:
        signals = db.scalars(
            select(LeadSignal)
            .where(LeadSignal.workspace_id == lead.workspace_id, LeadSignal.lead_id == lead.id)
            .order_by(LeadSignal.signal_strength.desc(), LeadSignal.id)
            .limit(_MAX_EVIDENCE)
        ).all()
        return [
            AuditEvidence(
                signal_type=signal.signal_type,
                text=signal.evidence_text.strip(),
                # Only web links are printed; anything else is not a source a
                # client can open.
                source_url=(
                    signal.source_url
                    if signal.source_url and signal.source_url.startswith(("https://", "http://"))
                    else None
                ),
            )
            for signal in signals
            if signal.evidence_text and signal.evidence_text.strip()
        ]
