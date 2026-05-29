from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.outreach.models import OutreachMessage


class OutreachRepository:
    def get_by_snapshot_id(
        self,
        db: Session,
        snapshot_id: int,
        *,
        tone: str | None = None,
    ) -> OutreachMessage | None:
        statement = (
            select(OutreachMessage)
            .where(OutreachMessage.ai_analysis_snapshot_id == snapshot_id)
            .order_by(OutreachMessage.version_number.desc(), OutreachMessage.id.desc())
            .limit(1)
        )
        if tone is not None:
            statement = statement.where(OutreachMessage.tone == tone)
        return db.scalar(statement)

    def get_latest_by_lead(self, db: Session, lead_id: int) -> OutreachMessage | None:
        statement = (
            select(OutreachMessage)
            .where(OutreachMessage.lead_id == lead_id)
            .order_by(OutreachMessage.version_number.desc(), OutreachMessage.id.desc())
            .limit(1)
        )
        return db.scalar(statement)

    def get_next_version_number(self, db: Session, lead_id: int) -> int:
        statement = select(func.max(OutreachMessage.version_number)).where(
            OutreachMessage.lead_id == lead_id
        )
        current = db.scalar(statement)
        return (int(current) if current is not None else 0) + 1

    def get_by_public_id(self, db: Session, public_id: str) -> OutreachMessage | None:
        statement = select(OutreachMessage).where(OutreachMessage.public_id == public_id).limit(1)
        return db.scalar(statement)

    def get_latest_outreach_statuses(
        self, db: Session, lead_ids: list[int]
    ) -> dict[int, str]:
        if not lead_ids:
            return {}
        subq = (
            select(
                OutreachMessage.lead_id,
                func.max(OutreachMessage.id).label("max_id"),
            )
            .where(OutreachMessage.lead_id.in_(lead_ids))
            .group_by(OutreachMessage.lead_id)
            .subquery()
        )
        statement = select(
            OutreachMessage.lead_id, OutreachMessage.outreach_status
        ).join(subq, OutreachMessage.id == subq.c.max_id)
        rows = db.execute(statement).all()
        return {row.lead_id: row.outreach_status for row in rows}

    def add(self, db: Session, message: OutreachMessage) -> OutreachMessage:
        db.add(message)
        db.commit()
        db.refresh(message)
        return message

    def save(self, db: Session, message: OutreachMessage) -> OutreachMessage:
        db.add(message)
        db.commit()
        db.refresh(message)
        return message
