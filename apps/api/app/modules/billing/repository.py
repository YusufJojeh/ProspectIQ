from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.modules.billing.models import (
    Invoice,
    InvoiceItem,
    PaymentAttempt,
    Plan,
    Subscription,
    UsageCounter,
)


class BillingRepository:
    def list_plans(self, db: Session) -> list[Plan]:
        return list(db.scalars(select(Plan).where(Plan.is_active.is_(True)).order_by(Plan.id.asc())))

    def get_plan_by_code(self, db: Session, code: str) -> Plan | None:
        return db.scalar(select(Plan).where(Plan.code == code))

    def get_subscription_for_workspace(self, db: Session, workspace_id: int) -> Subscription | None:
        return db.scalar(
            select(Subscription)
            .where(Subscription.workspace_id == workspace_id)
            .order_by(Subscription.id.desc())
        )

    def list_invoices_for_workspace(self, db: Session, workspace_id: int) -> list[Invoice]:
        return list(
            db.scalars(
                select(Invoice)
                .where(Invoice.workspace_id == workspace_id)
                .order_by(Invoice.issued_at.desc(), Invoice.id.desc())
            )
        )

    def get_invoice_for_workspace(self, db: Session, workspace_id: int, public_id: str) -> Invoice | None:
        return db.scalar(
            select(Invoice).where(Invoice.workspace_id == workspace_id, Invoice.public_id == public_id)
        )

    def get_plan(self, db: Session, plan_id: int) -> Plan | None:
        return db.scalar(select(Plan).where(Plan.id == plan_id))

    def add(self, db: Session, item):
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    def save(self, db: Session, item):
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    def save_all(self, db: Session, *items) -> None:
        for item in items:
            db.add(item)
        db.commit()

    def get_usage_counter(
        self,
        db: Session,
        *,
        workspace_id: int,
        metric_key: str,
        period_start: datetime,
        period_end: datetime,
    ) -> UsageCounter | None:
        return db.scalar(
            select(UsageCounter).where(
                and_(
                    UsageCounter.workspace_id == workspace_id,
                    UsageCounter.metric_key == metric_key,
                    UsageCounter.period_start == period_start,
                    UsageCounter.period_end == period_end,
                )
            )
        )

    def list_usage_for_workspace(self, db: Session, workspace_id: int) -> list[UsageCounter]:
        now = datetime.now(tz=UTC)
        return list(
            db.scalars(
                select(UsageCounter)
                .where(UsageCounter.workspace_id == workspace_id, UsageCounter.period_end >= now)
                .order_by(UsageCounter.metric_key.asc())
            )
        )

    def list_invoice_items(self, db: Session, invoice_id: int) -> list[InvoiceItem]:
        return list(
            db.scalars(select(InvoiceItem).where(InvoiceItem.invoice_id == invoice_id).order_by(InvoiceItem.id.asc()))
        )

    def list_payment_attempts(self, db: Session, invoice_id: int) -> list[PaymentAttempt]:
        return list(
            db.scalars(
                select(PaymentAttempt)
                .where(PaymentAttempt.invoice_id == invoice_id)
                .order_by(PaymentAttempt.attempted_at.desc(), PaymentAttempt.id.desc())
            )
        )
