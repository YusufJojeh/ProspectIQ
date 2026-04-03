from __future__ import annotations

import csv
from io import StringIO

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.modules.ai_analysis.models import AIAnalysisSnapshot, ServiceRecommendation
from app.modules.leads.models import Lead
from app.modules.leads.repository import LeadsRepository
from app.modules.leads.schemas import LeadSortOption
from app.modules.outreach.models import OutreachMessage
from app.modules.users.models import User


class ExportService:
    def __init__(self) -> None:
        self.leads = LeadsRepository()

    def export_leads_csv(
        self,
        db: Session,
        *,
        workspace_id: int,
        status: str | None = None,
        search_job_public_id: str | None = None,
        has_website: bool | None = None,
        q: str | None = None,
        city: str | None = None,
        band: str | None = None,
        category: str | None = None,
        min_score: float | None = None,
        max_score: float | None = None,
        qualified: bool | None = None,
        owner_public_id: str | None = None,
        lead_public_ids: list[str] | None = None,
        sort: LeadSortOption = LeadSortOption.NEWEST,
    ) -> str:
        leads = self.leads.list_all(
            db,
            workspace_id=workspace_id,
            status=status,
            search_job_public_id=search_job_public_id,
            has_website=has_website,
            q=q,
            city=city,
            band=band,
            category=category,
            min_score=min_score,
            max_score=max_score,
            qualified=qualified,
            owner_public_id=owner_public_id,
            lead_public_ids=lead_public_ids,
            sort=sort,
        )
        latest_scores = self.leads.get_latest_scores(db, [lead.id for lead in leads])
        latest_recommendations = self._latest_recommendations(db, [lead.id for lead in leads])
        latest_outreach = self._latest_outreach(db, [lead.id for lead in leads])
        owners = self._owner_lookup(db, leads)

        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "lead_id",
                "business_name",
                "category",
                "city",
                "rating",
                "review_count",
                "website",
                "lead_score",
                "qualification",
                "recommended_service",
                "outreach_tone",
                "outreach_subject",
                "outreach_message",
                "owner",
                "status",
            ]
        )
        for lead in leads:
            latest_score = latest_scores.get(lead.id)
            recommendation = latest_recommendations.get(lead.id)
            outreach = latest_outreach.get(lead.id)
            owner = (
                owners.get(lead.assigned_to_user_id)
                if lead.assigned_to_user_id is not None
                else None
            )
            writer.writerow(
                [
                    lead.public_id,
                    lead.company_name,
                    lead.category or "",
                    lead.city or "",
                    lead.rating or "",
                    lead.review_count,
                    lead.website_url or lead.website_domain or "",
                    latest_score.total_score if latest_score else "",
                    "qualified" if latest_score and latest_score.qualified else "not_qualified",
                    recommendation.service_name if recommendation else "",
                    outreach.tone if outreach else "",
                    (outreach.edited_subject or outreach.subject) if outreach else "",
                    (outreach.edited_message or outreach.message) if outreach else "",
                    owner.full_name if owner else "",
                    lead.status,
                ]
            )
        return buffer.getvalue()

    def _latest_recommendations(
        self, db: Session, lead_ids: list[int]
    ) -> dict[int, ServiceRecommendation]:
        if not lead_ids:
            return {}
        snapshot_subquery = (
            select(
                AIAnalysisSnapshot.lead_id.label("lead_id"),
                func.max(AIAnalysisSnapshot.created_at).label("max_created_at"),
            )
            .where(AIAnalysisSnapshot.lead_id.in_(lead_ids))
            .group_by(AIAnalysisSnapshot.lead_id)
            .subquery()
        )
        latest_snapshot_ids = (
            select(AIAnalysisSnapshot.id, AIAnalysisSnapshot.lead_id)
            .join(
                snapshot_subquery,
                and_(
                    AIAnalysisSnapshot.lead_id == snapshot_subquery.c.lead_id,
                    AIAnalysisSnapshot.created_at == snapshot_subquery.c.max_created_at,
                ),
            )
            .subquery()
        )
        statement = (
            select(ServiceRecommendation, latest_snapshot_ids.c.lead_id)
            .join(
                latest_snapshot_ids,
                ServiceRecommendation.ai_analysis_snapshot_id == latest_snapshot_ids.c.id,
            )
            .where(ServiceRecommendation.rank_order == 1)
        )
        rows = db.execute(statement).all()
        return {int(lead_id): item for item, lead_id in rows}

    def _latest_outreach(self, db: Session, lead_ids: list[int]) -> dict[int, OutreachMessage]:
        if not lead_ids:
            return {}
        version_subquery = (
            select(
                OutreachMessage.lead_id.label("lead_id"),
                func.max(OutreachMessage.version_number).label("max_version"),
            )
            .where(OutreachMessage.lead_id.in_(lead_ids))
            .group_by(OutreachMessage.lead_id)
            .subquery()
        )
        statement = select(OutreachMessage).join(
            version_subquery,
            and_(
                OutreachMessage.lead_id == version_subquery.c.lead_id,
                OutreachMessage.version_number == version_subquery.c.max_version,
            ),
        )
        items = list(db.scalars(statement))
        return {item.lead_id: item for item in items}

    def _owner_lookup(self, db: Session, leads: list[Lead]) -> dict[int, User]:
        owner_ids = {
            lead.assigned_to_user_id for lead in leads if lead.assigned_to_user_id is not None
        }
        if not owner_ids:
            return {}
        statement = select(User).where(User.id.in_(list(owner_ids)))
        items = list(db.scalars(statement))
        return {item.id: item for item in items}
