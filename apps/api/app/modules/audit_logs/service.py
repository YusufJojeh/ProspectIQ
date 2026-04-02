from sqlalchemy.orm import Session

from app.modules.audit_logs.models import AuditLog
from app.modules.audit_logs.repository import AuditLogsRepository


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
