from sqlalchemy.orm import Session

from app.modules.audit_logs.models import AuditLog


class AuditLogsRepository:
    def add(self, db: Session, log: AuditLog) -> AuditLog:
        db.add(log)
        db.commit()
        db.refresh(log)
        return log

