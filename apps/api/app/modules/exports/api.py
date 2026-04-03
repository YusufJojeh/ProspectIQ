from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.audit_logs.service import AuditLogService
from app.modules.auth.policies import get_current_user, get_current_workspace_id
from app.modules.exports.service import ExportService
from app.modules.users.models import User
from app.shared.enums.jobs import LeadScoreBand, LeadStatus

router = APIRouter(prefix="/api/v1/exports", tags=["exports"])


@router.get("/leads.csv")
def export_leads_csv(
    q: str | None = Query(default=None),
    city: str | None = Query(default=None),
    status: LeadStatus | None = Query(default=None),
    band: LeadScoreBand | None = Query(default=None),
    search_job_id: str | None = Query(default=None),
    has_website: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> Response:
    csv_payload = ExportService().export_leads_csv(
        db,
        workspace_id=workspace_id,
        status=status.value if status else None,
        search_job_public_id=search_job_id,
        has_website=has_website,
        q=q,
        city=city,
        band=band.value if band else None,
    )
    AuditLogService().record(
        db,
        workspace_id=workspace_id,
        actor_user_id=current_user.id,
        event_name="leads.exported_csv",
        details="Exported the current lead list as CSV.",
    )
    return Response(
        content=csv_payload,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="prospectiq-leads.csv"'},
    )
