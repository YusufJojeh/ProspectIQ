from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit_logs.models import AuditLog


class AuditLogsRepository:
    def add(self, db: Session, log: AuditLog) -> AuditLog:
        db.add(log)
        db.commit()
        db.refresh(log)
        return log

    def list_for_workspace(
        self, db: Session, workspace_id: int, *, limit: int = 50
    ) -> list[AuditLog]:
        statement = (
            select(AuditLog)
            .where(AuditLog.workspace_id == workspace_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        return list(db.scalars(statement))
