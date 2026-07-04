from __future__ import annotations

import csv
import json
from io import StringIO
from typing import Any, Literal

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.modules.ai_analysis.models import AIAnalysisSnapshot, ServiceRecommendation
from app.modules.audit_logs.service import AuditLogService
from app.modules.billing.service import BillingService
from app.modules.leads.models import Lead
from app.modules.leads.repository import LeadsRepository
from app.modules.leads.schemas import LeadSortOption
from app.modules.outreach.models import OutreachMessage
from app.modules.users.models import User


class ExportService:
    def __init__(self) -> None:
        self.leads = LeadsRepository()
        self.billing = BillingService()
        self.audit_logs = AuditLogService()

    def export_with_billing(
        self,
        db: Session,
        *,
        workspace_id: int,
        actor_user_id: int,
        fmt: Literal["csv", "json"] = "csv",
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
        self.billing.enforce_usage(
            db,
            workspace_id=workspace_id,
            metric_key="exports_per_month",
            actor_user_id=actor_user_id,
        )
        rows = self._collect_rows(
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
        if fmt == "json":
            payload = self._rows_to_json(rows)
            event_name, details = "leads.exported_json", "Exported the current lead list as JSON."
        else:
            payload = self._rows_to_csv(rows)
            event_name, details = "leads.exported_csv", "Exported the current lead list as CSV."
        self.audit_logs.record(
            db,
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            event_name=event_name,
            details=details,
        )
        self.billing.record_usage(db, workspace_id=workspace_id, metric_key="exports_per_month")
        return payload

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
        return self._rows_to_csv(
            self._collect_rows(
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
        )

    def export_leads_json(
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
        return self._rows_to_json(
            self._collect_rows(
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
        )

    def _collect_rows(
        self,
        db: Session,
        *,
        workspace_id: int,
        status: str | None,
        search_job_public_id: str | None,
        has_website: bool | None,
        q: str | None,
        city: str | None,
        band: str | None,
        category: str | None,
        min_score: float | None,
        max_score: float | None,
        qualified: bool | None,
        owner_public_id: str | None,
        lead_public_ids: list[str] | None,
        sort: LeadSortOption,
    ) -> list[dict[str, Any]]:
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

        rows: list[dict[str, Any]] = []
        for lead in leads:
            latest_score = latest_scores.get(lead.id)
            recommendation = latest_recommendations.get(lead.id)
            outreach = latest_outreach.get(lead.id)
            owner = (
                owners.get(lead.assigned_to_user_id)
                if lead.assigned_to_user_id is not None
                else None
            )
            rows.append(
                {
                    "lead_id": lead.public_id,
                    "business_name": lead.company_name,
                    "category": lead.category,
                    "industry": lead.industry,
                    "city": lead.city,
                    "rating": lead.rating,
                    "review_count": lead.review_count,
                    "website": lead.website_url or lead.website_domain,
                    "email": lead.email,
                    "email_confidence": lead.email_confidence,
                    "linkedin_url": lead.linkedin_url,
                    "employee_count": lead.employee_count,
                    "logo_url": lead.logo_url,
                    "lead_score": latest_score.total_score if latest_score else None,
                    "qualification": (
                        "qualified" if latest_score and latest_score.qualified else "not_qualified"
                    ),
                    "recommended_service": (
                        recommendation.service_name if recommendation else None
                    ),
                    "ai_opener": lead.ai_opener,
                    "outreach_tone": outreach.tone if outreach else None,
                    "outreach_subject": (
                        (outreach.edited_subject or outreach.subject) if outreach else None
                    ),
                    "outreach_message": (
                        (outreach.edited_message or outreach.message) if outreach else None
                    ),
                    "owner": owner.full_name if owner else None,
                    "status": lead.status,
                }
            )
        return rows

    @staticmethod
    def _rows_to_csv(rows: list[dict[str, Any]]) -> str:
        columns = [
            "lead_id",
            "business_name",
            "category",
            "industry",
            "city",
            "rating",
            "review_count",
            "website",
            "email",
            "email_confidence",
            "linkedin_url",
            "employee_count",
            "logo_url",
            "lead_score",
            "qualification",
            "recommended_service",
            "ai_opener",
            "outreach_tone",
            "outreach_subject",
            "outreach_message",
            "owner",
            "status",
        ]
        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow(columns)
        for row in rows:
            writer.writerow(["" if row.get(col) is None else row.get(col) for col in columns])
        return buffer.getvalue()

    @staticmethod
    def _rows_to_json(rows: list[dict[str, Any]]) -> str:
        return json.dumps({"items": rows, "count": len(rows)}, ensure_ascii=False, default=str)

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
