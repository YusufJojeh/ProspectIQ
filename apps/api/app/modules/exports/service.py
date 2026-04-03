from __future__ import annotations

import csv
from io import StringIO

from sqlalchemy.orm import Session

from app.modules.leads.repository import LeadsRepository


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
        )
        latest_scores = self.leads.get_latest_scores(db, [lead.id for lead in leads])

        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "lead_id",
                "company_name",
                "category",
                "city",
                "address",
                "phone",
                "website_url",
                "website_domain",
                "review_count",
                "rating",
                "has_website",
                "data_completeness",
                "data_confidence",
                "latest_score",
                "latest_band",
                "status",
                "created_at",
                "updated_at",
            ]
        )
        for lead in leads:
            latest = latest_scores.get(lead.id)
            writer.writerow(
                [
                    lead.public_id,
                    lead.company_name,
                    lead.category or "",
                    lead.city or "",
                    lead.address or "",
                    lead.phone or "",
                    lead.website_url or "",
                    lead.website_domain or "",
                    lead.review_count,
                    lead.rating or "",
                    "yes" if lead.has_website else "no",
                    lead.data_completeness,
                    lead.data_confidence,
                    latest.total_score if latest else "",
                    latest.band if latest else "",
                    lead.status,
                    lead.created_at.isoformat(),
                    lead.updated_at.isoformat(),
                ]
            )
        return buffer.getvalue()
