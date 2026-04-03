from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.outreach.models import OutreachMessage


class OutreachRepository:
    def get_by_snapshot_id(self, db: Session, snapshot_id: int) -> OutreachMessage | None:
        statement = (
            select(OutreachMessage)
            .where(OutreachMessage.ai_analysis_snapshot_id == snapshot_id)
            .order_by(OutreachMessage.created_at.desc())
            .limit(1)
        )
        return db.scalar(statement)

    def get_latest_by_lead(self, db: Session, lead_id: int) -> OutreachMessage | None:
        statement = (
            select(OutreachMessage)
            .where(OutreachMessage.lead_id == lead_id)
            .order_by(OutreachMessage.updated_at.desc(), OutreachMessage.id.desc())
            .limit(1)
        )
        return db.scalar(statement)

    def get_by_public_id(self, db: Session, public_id: str) -> OutreachMessage | None:
        statement = select(OutreachMessage).where(OutreachMessage.public_id == public_id).limit(1)
        return db.scalar(statement)

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
