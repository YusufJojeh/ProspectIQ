from sqlalchemy.orm import Session

from app.modules.audit_logs.models import AuditLog
from app.modules.audit_logs.repository import AuditLogsRepository
from app.modules.audit_logs.schemas import AuditLogListResponse, AuditLogResponse
from app.modules.users.models import User


class AuditLogService:
    def __init__(self) -> None:
        self.repository = AuditLogsRepository()

    def record(
        self,
        db: Session,
        *,
        workspace_id: int,
        event_name: str,
        details: str,
        actor_user_id: int | None = None,
    ) -> AuditLog:
        return self.repository.add(
            db,
            AuditLog(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                event_name=event_name,
                details=details,
            ),
        )

    def list_entries(
        self, db: Session, *, workspace_id: int, limit: int = 50
    ) -> AuditLogListResponse:
        items = self.repository.list_for_workspace(db, workspace_id, limit=limit)
        actor_ids = {item.actor_user_id for item in items if item.actor_user_id is not None}
        actors = (
            {
                user.id: user.public_id
                for user in db.query(User).filter(User.id.in_(list(actor_ids))).all()
            }
            if actor_ids
            else {}
        )
        return AuditLogListResponse(
            items=[
                AuditLogResponse(
                    public_id=item.public_id,
                    actor_user_public_id=actors.get(item.actor_user_id)
                    if item.actor_user_id
                    else None,
                    event_name=item.event_name,
                    details=item.details,
                    created_at=item.created_at,
                )
                for item in items
            ]
        )
