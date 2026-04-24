from __future__ import annotations

from calendar import monthrange
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.modules.audit_logs.service import AuditLogService
from app.modules.auth.permissions import assert_workspace_permission
from app.modules.billing.exceptions import PlanLimitExceededError, SubscriptionAccessError
from app.modules.billing.models import Invoice, InvoiceItem, PaymentAttempt, Plan, Subscription, UsageCounter
from app.modules.billing.repository import BillingRepository
from app.modules.billing.schemas import (
    InvoiceItemResponse,
    InvoiceListResponse,
    InvoiceResponse,
    PaymentAttemptResponse,
    PlanListResponse,
    PlanResponse,
    SubscriptionChangeRequest,
    SubscriptionResponse,
    UsageMetricResponse,
    UsageSummaryResponse,
)
from app.modules.users.models import User, Workspace
from app.modules.users.repository import UsersRepository


DEFAULT_PLAN_DEFINITIONS = [
    {
        "code": "starter",
        "name": "Starter",
        "monthly_price": Decimal("49.00"),
        "yearly_price": Decimal("490.00"),
        "limits_json": {
            "searches_per_month": 50,
            "exports_per_month": 25,
            "ai_scoring_runs_per_month": 100,
            "outreach_generations_per_month": 150,
            "max_team_users": 3,
        },
    },
    {
        "code": "growth",
        "name": "Growth",
        "monthly_price": Decimal("149.00"),
        "yearly_price": Decimal("1490.00"),
        "limits_json": {
            "searches_per_month": 250,
            "exports_per_month": 100,
            "ai_scoring_runs_per_month": 500,
            "outreach_generations_per_month": 700,
            "max_team_users": 10,
        },
    },
    {
        "code": "pro",
        "name": "Pro",
        "monthly_price": Decimal("399.00"),
        "yearly_price": Decimal("3990.00"),
        "limits_json": {
            "searches_per_month": 1000,
            "exports_per_month": 500,
            "ai_scoring_runs_per_month": 2000,
            "outreach_generations_per_month": 3000,
            "max_team_users": 30,
        },
    },
    {
        "code": "enterprise",
        "name": "Enterprise",
        "monthly_price": Decimal("999.00"),
        "yearly_price": Decimal("9990.00"),
        "limits_json": {
            "searches_per_month": 5000,
            "exports_per_month": 2500,
            "ai_scoring_runs_per_month": 10000,
            "outreach_generations_per_month": 15000,
            "max_team_users": 200,
        },
    },
]


class BillingService:
    def __init__(self) -> None:
        self.repository = BillingRepository()
        self.users_repository = UsersRepository()
        self.audit_logs = AuditLogService()

    def ensure_seed_data(self, db: Session) -> None:
        existing_codes = {plan.code for plan in self.repository.list_plans(db)}
        missing = [
            Plan(**definition)
            for definition in DEFAULT_PLAN_DEFINITIONS
            if definition["code"] not in existing_codes
        ]
        if missing:
            self.repository.save_all(db, *missing)

    def bootstrap_workspace_subscription(
        self, db: Session, *, workspace: Workspace, actor_user_id: int
    ) -> Subscription:
        self.ensure_seed_data(db)
        current = self.repository.get_subscription_for_workspace(db, workspace.id)
        if current is not None:
            return current
        starter = self.repository.get_plan_by_code(db, "starter")
        assert starter is not None
        now = datetime.now(tz=UTC)
        trial_ends_at = now + timedelta(days=14)
        subscription = Subscription(
            workspace_id=workspace.id,
            plan_id=starter.id,
            status="trialing",
            billing_cycle="monthly",
            started_at=now,
            renews_at=trial_ends_at,
            trial_ends_at=trial_ends_at,
            updated_at=now,
        )
        db.add(subscription)
        db.flush()
        invoice = Invoice(
            workspace_id=workspace.id,
            subscription_id=subscription.id,
            amount=starter.monthly_price,
            currency="USD",
            status="paid",
            issued_at=now,
            due_at=trial_ends_at,
            paid_at=now,
        )
        db.add(invoice)
        db.flush()
        db.add(
            InvoiceItem(
                invoice_id=invoice.id,
                description=f"{starter.name} plan trial bootstrap",
                amount=starter.monthly_price,
                quantity=1,
            )
        )
        db.commit()
        db.refresh(subscription)
        self.audit_logs.record(
            db,
            workspace_id=workspace.id,
            actor_user_id=actor_user_id,
            event_name="billing.subscription_created",
            details=f"Created simulated starter subscription {subscription.public_id}.",
        )
        return subscription

    def list_plans(self, db: Session) -> PlanListResponse:
        self.ensure_seed_data(db)
        return PlanListResponse(items=[self._to_plan_response(item) for item in self.repository.list_plans(db)])

    def get_subscription(self, db: Session, *, workspace_id: int) -> SubscriptionResponse:
        subscription = self._get_subscription_or_raise(db, workspace_id)
        plan = self._get_plan_or_raise(db, subscription.plan_id)
        return self._to_subscription_response(subscription, plan)

    def list_invoices(self, db: Session, *, workspace_id: int) -> InvoiceListResponse:
        invoices = self.repository.list_invoices_for_workspace(db, workspace_id)
        return InvoiceListResponse(items=[self._to_invoice_response(db, item) for item in invoices])

    def get_usage_summary(self, db: Session, *, workspace_id: int) -> UsageSummaryResponse:
        subscription = self._get_subscription_or_raise(db, workspace_id)
        plan = self._get_plan_or_raise(db, subscription.plan_id)
        period_start, period_end = self.current_month_period()
        items: list[UsageMetricResponse] = []
        counters = {item.metric_key: item for item in self.repository.list_usage_for_workspace(db, workspace_id)}
        for metric_key, limit_value in plan.limits_json.items():
            current_value = 0
            if metric_key == "max_team_users":
                current_value = self.users_repository.count_for_workspace(db, workspace_id)
            else:
                current_value = counters.get(metric_key, self._empty_usage_counter(workspace_id, metric_key, period_start, period_end)).current_value
            items.append(
                UsageMetricResponse(
                    metric_key=metric_key,
                    current_value=current_value,
                    limit_value=limit_value,
                    period_start=period_start,
                    period_end=period_end,
                )
            )
        return UsageSummaryResponse(items=items)

    def enforce_usage(self, db: Session, *, workspace_id: int, metric_key: str, actor_user_id: int | None = None) -> None:
        subscription = self._get_subscription_or_raise(
            db,
            workspace_id,
            actor_user_id=actor_user_id,
        )
        if not self._is_subscription_operational(subscription):
            raise SubscriptionAccessError("The current subscription status does not allow this action.")
        plan = self._get_plan_or_raise(db, subscription.plan_id)
        limit_value = plan.limits_json.get(metric_key)
        if limit_value is None:
            return
        period_start, period_end = self.current_month_period()
        if metric_key == "max_team_users":
            current_value = self.users_repository.count_for_workspace(db, workspace_id)
        else:
            counter = self._get_or_create_usage_counter(
                db,
                workspace_id=workspace_id,
                metric_key=metric_key,
                period_start=period_start,
                period_end=period_end,
            )
            current_value = counter.current_value
        if current_value >= limit_value:
            self.audit_logs.record(
                db,
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                event_name="billing.plan_limit_denied",
                details=f"Denied metric {metric_key}; usage {current_value} / {limit_value}.",
            )
            raise PlanLimitExceededError(
                f"Your current plan limit for {metric_key.replace('_', ' ')} has been reached. Upgrade to continue."
            )

    def record_usage(self, db: Session, *, workspace_id: int, metric_key: str) -> UsageCounter:
        period_start, period_end = self.current_month_period()
        counter = self._get_or_create_usage_counter(
            db,
            workspace_id=workspace_id,
            metric_key=metric_key,
            period_start=period_start,
            period_end=period_end,
        )
        counter.current_value += 1
        counter.updated_at = datetime.now(tz=UTC)
        return self.repository.save(db, counter)

    def change_subscription(
        self,
        db: Session,
        *,
        workspace_id: int,
        payload: SubscriptionChangeRequest,
        actor: User,
    ) -> SubscriptionResponse:
        self._assert_owner(actor)
        subscription = self._get_subscription_or_raise(
            db,
            workspace_id,
            actor_user_id=actor.id,
        )
        plan = self.repository.get_plan_by_code(db, payload.plan_code)
        if plan is None:
            raise NotFoundError("Plan was not found.")
        now = datetime.now(tz=UTC)
        subscription.plan_id = plan.id
        subscription.billing_cycle = payload.billing_cycle
        if subscription.status not in {"trialing", "past_due"}:
            subscription.status = "active"
        subscription.ends_at = None
        subscription.canceled_at = None
        subscription.renews_at = self._next_renewal_at(now, payload.billing_cycle)
        subscription.updated_at = now
        self.repository.save(db, subscription)
        invoice_amount = plan.yearly_price if payload.billing_cycle == "yearly" else plan.monthly_price
        self._create_invoice(
            db,
            workspace_id=workspace_id,
            subscription=subscription,
            description=f"{plan.name} plan change ({payload.billing_cycle})",
            amount=invoice_amount,
        )
        self.audit_logs.record(
            db,
            workspace_id=workspace_id,
            actor_user_id=actor.id,
            event_name="billing.subscription_changed",
            details=f"Changed subscription {subscription.public_id} to {plan.code} ({payload.billing_cycle}).",
        )
        return self._to_subscription_response(subscription, plan)

    def cancel_subscription(self, db: Session, *, workspace_id: int, actor: User) -> SubscriptionResponse:
        self._assert_owner(actor)
        subscription = self._get_subscription_or_raise(
            db,
            workspace_id,
            actor_user_id=actor.id,
        )
        now = datetime.now(tz=UTC)
        if subscription.renews_at is None:
            subscription.renews_at = self._next_renewal_at(now, subscription.billing_cycle)
        subscription.status = "canceled"
        subscription.canceled_at = now
        subscription.ends_at = subscription.renews_at
        subscription.updated_at = now
        self.repository.save(db, subscription)
        plan = self._get_plan_or_raise(db, subscription.plan_id)
        self.audit_logs.record(
            db,
            workspace_id=workspace_id,
            actor_user_id=actor.id,
            event_name="billing.subscription_canceled",
            details=f"Canceled subscription {subscription.public_id}.",
        )
        return self._to_subscription_response(subscription, plan)

    def renew_subscription(self, db: Session, *, workspace_id: int, actor: User) -> SubscriptionResponse:
        self._assert_owner(actor)
        subscription = self._get_subscription_or_raise(
            db,
            workspace_id,
            actor_user_id=actor.id,
        )
        now = datetime.now(tz=UTC)
        subscription.status = "active"
        subscription.canceled_at = None
        subscription.ends_at = None
        subscription.renews_at = self._next_renewal_at(now, subscription.billing_cycle)
        subscription.updated_at = now
        self.repository.save(db, subscription)
        plan = self._get_plan_or_raise(db, subscription.plan_id)
        renewal_amount = plan.yearly_price if subscription.billing_cycle == "yearly" else plan.monthly_price
        self._create_invoice(
            db,
            workspace_id=workspace_id,
            subscription=subscription,
            description=f"{plan.name} plan renewal ({subscription.billing_cycle})",
            amount=renewal_amount,
        )
        self.audit_logs.record(
            db,
            workspace_id=workspace_id,
            actor_user_id=actor.id,
            event_name="billing.subscription_renewed",
            details=f"Renewed subscription {subscription.public_id}.",
        )
        return self._to_subscription_response(subscription, plan)

    def mark_invoice_paid(self, db: Session, *, workspace_id: int, invoice_public_id: str, actor: User) -> InvoiceResponse:
        self._assert_owner(actor)
        invoice = self.repository.get_invoice_for_workspace(db, workspace_id, invoice_public_id)
        if invoice is None:
            raise NotFoundError("Invoice was not found.")
        now = datetime.now(tz=UTC)
        invoice.status = "paid"
        invoice.paid_at = now
        self.repository.save(db, invoice)
        db.add(PaymentAttempt(invoice_id=invoice.id, status="succeeded", simulated_result="success"))
        db.commit()
        subscription = self._get_subscription_or_raise(
            db,
            workspace_id,
            actor_user_id=actor.id,
        )
        subscription.status = "active"
        subscription.ends_at = None
        subscription.canceled_at = None
        subscription.renews_at = self._next_renewal_at(now, subscription.billing_cycle)
        subscription.updated_at = now
        self.repository.save(db, subscription)
        self.audit_logs.record(
            db,
            workspace_id=workspace_id,
            actor_user_id=actor.id,
            event_name="billing.invoice_paid",
            details=f"Marked invoice {invoice.public_id} as paid.",
        )
        return self._to_invoice_response(db, invoice)

    def simulate_payment_failure(
        self,
        db: Session,
        *,
        workspace_id: int,
        invoice_public_id: str,
        actor: User,
        error_message: str | None = None,
    ) -> InvoiceResponse:
        self._assert_owner(actor)
        invoice = self.repository.get_invoice_for_workspace(db, workspace_id, invoice_public_id)
        if invoice is None:
            raise NotFoundError("Invoice was not found.")
        now = datetime.now(tz=UTC)
        invoice.status = "past_due"
        invoice.paid_at = None
        self.repository.save(db, invoice)
        db.add(
            PaymentAttempt(
                invoice_id=invoice.id,
                status="failed",
                simulated_result="failure",
                error_message=error_message or "Simulated payment failure.",
            )
        )
        db.commit()
        subscription = self._get_subscription_or_raise(
            db,
            workspace_id,
            actor_user_id=actor.id,
        )
        subscription.status = "past_due"
        subscription.ends_at = subscription.renews_at
        subscription.updated_at = now
        self.repository.save(db, subscription)
        self.audit_logs.record(
            db,
            workspace_id=workspace_id,
            actor_user_id=actor.id,
            event_name="billing.payment_failed",
            details=f"Simulated a failed payment for invoice {invoice.public_id}.",
        )
        return self._to_invoice_response(db, invoice)

    def _create_invoice(
        self,
        db: Session,
        *,
        workspace_id: int,
        subscription: Subscription,
        description: str,
        amount: Decimal,
    ) -> Invoice:
        invoice = Invoice(
            workspace_id=workspace_id,
            subscription_id=subscription.id,
            amount=amount,
            currency="USD",
            status="open",
            issued_at=datetime.now(tz=UTC),
            due_at=datetime.now(tz=UTC) + timedelta(days=7),
        )
        db.add(invoice)
        db.flush()
        db.add(InvoiceItem(invoice_id=invoice.id, description=description, amount=amount, quantity=1))
        db.commit()
        db.refresh(invoice)
        return invoice

    def _get_subscription_or_raise(
        self,
        db: Session,
        workspace_id: int,
        *,
        actor_user_id: int | None = None,
    ) -> Subscription:
        subscription = self.repository.get_subscription_for_workspace(db, workspace_id)
        if subscription is not None:
            return subscription
        # Backfill-safe behavior: legacy workspaces can bootstrap simulated billing lazily.
        workspace = self.users_repository.get_workspace_by_id(db, workspace_id)
        if workspace is None:
            raise NotFoundError("Workspace was not found.")
        owner_id = actor_user_id or workspace.owner_user_id
        if owner_id is None:
            owner = db.scalar(
                select(User.id)
                .where(User.workspace_id == workspace_id)
                .order_by(User.created_at.asc(), User.id.asc())
                .limit(1)
            )
            owner_id = owner
        if owner_id is None:
            raise NotFoundError("Subscription was not found.")
        return self.bootstrap_workspace_subscription(
            db,
            workspace=workspace,
            actor_user_id=owner_id,
        )

    def _get_plan_or_raise(self, db: Session, plan_id: int) -> Plan:
        plan = self.repository.get_plan(db, plan_id)
        if plan is None:
            raise NotFoundError("Plan was not found.")
        return plan

    def _is_subscription_operational(self, subscription: Subscription) -> bool:
        return subscription.status in {"trialing", "active", "canceled"}

    def _assert_owner(self, actor: User) -> None:
        assert_workspace_permission(
            actor.role,
            "billing:manage",
            message="Only the account owner can change billing state.",
        )

    @staticmethod
    def _next_renewal_at(now: datetime, billing_cycle: str) -> datetime:
        if billing_cycle == "yearly":
            return now + timedelta(days=365)
        return now + timedelta(days=30)

    def _get_or_create_usage_counter(
        self,
        db: Session,
        *,
        workspace_id: int,
        metric_key: str,
        period_start: datetime,
        period_end: datetime,
    ) -> UsageCounter:
        counter = self.repository.get_usage_counter(
            db,
            workspace_id=workspace_id,
            metric_key=metric_key,
            period_start=period_start,
            period_end=period_end,
        )
        if counter is not None:
            return counter
        counter = UsageCounter(
            workspace_id=workspace_id,
            metric_key=metric_key,
            current_value=0,
            period_start=period_start,
            period_end=period_end,
        )
        db.add(counter)
        db.commit()
        db.refresh(counter)
        return counter

    def _empty_usage_counter(
        self, workspace_id: int, metric_key: str, period_start: datetime, period_end: datetime
    ) -> UsageCounter:
        return UsageCounter(
            workspace_id=workspace_id,
            metric_key=metric_key,
            current_value=0,
            period_start=period_start,
            period_end=period_end,
        )

    def _to_plan_response(self, plan: Plan) -> PlanResponse:
        return PlanResponse(
            code=plan.code,
            name=plan.name,
            monthly_price=float(plan.monthly_price),
            yearly_price=float(plan.yearly_price),
            limits=plan.limits_json,
            is_active=plan.is_active,
        )

    def _to_subscription_response(self, subscription: Subscription, plan: Plan) -> SubscriptionResponse:
        return SubscriptionResponse(
            public_id=subscription.public_id,
            plan_code=plan.code,
            plan_name=plan.name,
            status=subscription.status,
            billing_cycle=subscription.billing_cycle,
            started_at=subscription.started_at,
            ends_at=subscription.ends_at,
            renews_at=subscription.renews_at,
            canceled_at=subscription.canceled_at,
            trial_ends_at=subscription.trial_ends_at,
        )

    def _to_invoice_response(self, db: Session, invoice: Invoice) -> InvoiceResponse:
        items = self.repository.list_invoice_items(db, invoice.id)
        attempts = self.repository.list_payment_attempts(db, invoice.id)
        return InvoiceResponse(
            public_id=invoice.public_id,
            amount=float(invoice.amount),
            currency=invoice.currency,
            status=invoice.status,
            issued_at=invoice.issued_at,
            due_at=invoice.due_at,
            paid_at=invoice.paid_at,
            items=[
                InvoiceItemResponse(
                    description=item.description,
                    amount=float(item.amount),
                    quantity=item.quantity,
                )
                for item in items
            ],
            payment_attempts=[
                PaymentAttemptResponse(
                    public_id=item.public_id,
                    status=item.status,
                    simulated_result=item.simulated_result,
                    attempted_at=item.attempted_at,
                    error_message=item.error_message,
                )
                for item in attempts
            ],
        )

    @staticmethod
    def current_month_period() -> tuple[datetime, datetime]:
        now = datetime.now(tz=UTC)
        period_start = datetime(now.year, now.month, 1, tzinfo=UTC)
        last_day = monthrange(now.year, now.month)[1]
        period_end = datetime(now.year, now.month, last_day, 23, 59, 59, tzinfo=UTC)
        return period_start, period_end
