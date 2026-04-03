from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.audit_logs.schemas import AuditLogListResponse
from app.modules.audit_logs.service import AuditLogService
from app.modules.auth.policies import get_current_workspace_id, require_role
from app.modules.users.models import User

router = APIRouter(prefix="/api/v1/audit-logs", tags=["audit-logs"])


@router.get("", response_model=AuditLogListResponse)
def list_audit_logs(
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    workspace_id: int = Depends(get_current_workspace_id),
    _: User = Depends(require_role("admin")),
) -> AuditLogListResponse:
    return AuditLogService().list_entries(db, workspace_id=workspace_id, limit=limit)
