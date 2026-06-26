from __future__ import annotations

# ruff: noqa: E402
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.modules.ai_analysis.models import AIAnalysisEvidence, AIAnalysisSnapshot, AIFeedback
from app.modules.audit_logs.models import AuditLog
from app.modules.billing.models import (
    Invoice,
    InvoiceItem,
    PaymentAttempt,
    Plan,
    Subscription,
    UsageCounter,
)
from app.modules.icp.models import IcpProfile, LeadIcpMatch
from app.modules.leads.models import Lead
from app.modules.outreach.models import OutreachMessage
from app.modules.provider_serpapi.models import ProviderFetch, ProviderNormalizedFact
from app.modules.scoring.models import LeadScore, ScoreBreakdown
from app.modules.signals.models import LeadSignal, LeadSignalScore
from app.modules.users.models import User, Workspace
from app.modules.users.service import ensure_default_roles, normalize_workspace_slug
from scripts.seed import (
    _seed_demo_workspace,
    ensure_base_workspace_configuration,
    run_migrations,
)

DEMO_PLATFORM_EMAIL = "platform-admin@example.test"
DEMO_PLATFORM_PASSWORD = "PlatformAdmin123!"
DEMO_OWNER_EMAIL = "admin@example.test"
DEMO_OWNER_PASSWORD = "AdminPass123!"
DEMO_MANAGER_EMAIL = "manager@example.test"
DEMO_MANAGER_PASSWORD = "ManagerPass123!"
DEMO_MEMBER_EMAIL = "user1@example.test"
DEMO_MEMBER_PASSWORD = "UserPass123!"
DISABLED_OWNER_EMAIL = "disabled-owner@example.test"
DISABLED_OWNER_PASSWORD = "DisabledOwner123!"

ACTIVE_WORKSPACE_PUBLIC_ID = "ws_default"
PLATFORM_WORKSPACE_PUBLIC_ID = "ws_platform_ops"
DISABLED_WORKSPACE_PUBLIC_ID = "ws_demo_disabled"


@dataclass(frozen=True)
class DemoSeedSummary:
    platform_workspace: Workspace
    active_workspace: Workspace
    disabled_workspace: Workspace
    platform_admin: User
    owner: User
    manager: User
    member: User
    disabled_owner: User
    leads_count: int
    signals_count: int
    signal_scores_count: int
    icp_profiles_count: int
    icp_matches_count: int
    provider_fetches_count: int
    provider_facts_count: int
    provider_errors_count: int
    scoring_breakdowns_count: int
    ai_snapshots_count: int
    ai_evidence_count: int
    ai_feedback_count: int
    outreach_drafts_count: int
    outreach_sent_count: int
    usage_counters_count: int


def _ensure_workspace(
    db: Session,
    *,
    public_id: str,
    name: str,
    slug: str,
    status: Literal["active", "disabled"],
) -> Workspace:
    workspace = db.scalar(select(Workspace).where(Workspace.public_id == public_id))
    if workspace is None:
        workspace = Workspace(
            public_id=public_id,
            name=name,
            slug=normalize_workspace_slug(slug),
            status=status,
            settings_json={"locale": "en-US", "demo": True},
        )
    else:
        workspace.name = name
        workspace.slug = normalize_workspace_slug(slug)
        workspace.status = status
        workspace.settings_json = {**(workspace.settings_json or {}), "demo": True}
        workspace.updated_at = datetime.now(tz=UTC)
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return workspace


def _ensure_demo_user(
    db: Session,
    *,
    workspace_id: int,
    email: str,
    full_name: str,
    password: str,
    role: str,
) -> User:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None:
        user = User(
            workspace_id=workspace_id,
            email=email.lower(),
            full_name=full_name,
            hashed_password=hash_password(password),
            role=role,
            status="active",
        )
    else:
        user.workspace_id = workspace_id
        user.full_name = full_name
        user.hashed_password = hash_password(password)
        user.role = role
        user.status = "active"
        user.updated_at = datetime.now(tz=UTC)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _ensure_plan(
    db: Session,
    *,
    code: str,
    name: str,
    monthly_price: Decimal,
    yearly_price: Decimal,
    limits_json: dict[str, int],
) -> Plan:
    plan = db.scalar(select(Plan).where(Plan.code == code))
    if plan is None:
        plan = Plan(code=code, name=name)
    plan.name = name
    plan.monthly_price = monthly_price
    plan.yearly_price = yearly_price
    plan.limits_json = limits_json
    plan.is_active = True
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def _ensure_subscription(
    db: Session,
    *,
    public_id: str,
    workspace_id: int,
    plan_id: int,
    status: str,
    billing_cycle: str,
    started_at: datetime,
    renews_at: datetime | None,
) -> Subscription:
    subscription = db.scalar(select(Subscription).where(Subscription.public_id == public_id))
    if subscription is None:
        subscription = Subscription(public_id=public_id, workspace_id=workspace_id, plan_id=plan_id)
    subscription.workspace_id = workspace_id
    subscription.plan_id = plan_id
    subscription.status = status
    subscription.billing_cycle = billing_cycle
    subscription.started_at = started_at
    subscription.renews_at = renews_at
    subscription.trial_ends_at = started_at + timedelta(days=14) if status == "trialing" else None
    subscription.canceled_at = None
    subscription.updated_at = datetime.now(tz=UTC)
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription


def _ensure_invoice(
    db: Session,
    *,
    public_id: str,
    workspace_id: int,
    subscription_id: int,
    amount: Decimal,
    status: str,
    issued_at: datetime,
    item_description: str,
    payment_status: str,
    payment_result: str,
    payment_error: str | None = None,
) -> Invoice:
    invoice = db.scalar(select(Invoice).where(Invoice.public_id == public_id))
    if invoice is None:
        invoice = Invoice(
            public_id=public_id,
            workspace_id=workspace_id,
            subscription_id=subscription_id,
        )
    invoice.workspace_id = workspace_id
    invoice.subscription_id = subscription_id
    invoice.amount = amount
    invoice.currency = "USD"
    invoice.status = status
    invoice.issued_at = issued_at
    invoice.due_at = issued_at + timedelta(days=14)
    invoice.paid_at = issued_at + timedelta(days=1) if status == "paid" else None
    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    existing_items = list(
        db.scalars(select(InvoiceItem).where(InvoiceItem.invoice_id == invoice.id))
    )
    if existing_items:
        item = existing_items[0]
        for stale in existing_items[1:]:
            db.delete(stale)
    else:
        item = InvoiceItem(invoice_id=invoice.id, description=item_description)
    item.description = item_description
    item.amount = amount
    item.quantity = 1
    db.add(item)

    payment = db.scalar(
        select(PaymentAttempt).where(PaymentAttempt.public_id == f"pay_{public_id}")
    )
    if payment is None:
        payment = PaymentAttempt(public_id=f"pay_{public_id}", invoice_id=invoice.id)
    payment.invoice_id = invoice.id
    payment.status = payment_status
    payment.simulated_result = payment_result
    payment.error_message = payment_error
    payment.attempted_at = issued_at + timedelta(hours=6)
    db.add(payment)
    db.commit()
    return invoice


def _ensure_usage_counter(
    db: Session,
    *,
    workspace_id: int,
    metric_key: str,
    current_value: int,
    period_start: datetime,
    period_end: datetime,
) -> UsageCounter:
    counter = db.scalar(
        select(UsageCounter).where(
            UsageCounter.workspace_id == workspace_id,
            UsageCounter.metric_key == metric_key,
            UsageCounter.period_start == period_start,
            UsageCounter.period_end == period_end,
        )
    )
    if counter is None:
        counter = UsageCounter(
            workspace_id=workspace_id,
            metric_key=metric_key,
            period_start=period_start,
            period_end=period_end,
        )
    counter.current_value = current_value
    counter.updated_at = datetime.now(tz=UTC)
    db.add(counter)
    db.commit()
    db.refresh(counter)
    return counter


def _ensure_audit_log(
    db: Session,
    *,
    workspace_id: int,
    actor_user_id: int | None,
    event_name: str,
    details: str,
) -> None:
    exists = db.scalar(
        select(AuditLog.id)
        .where(
            AuditLog.workspace_id == workspace_id,
            AuditLog.actor_user_id == actor_user_id,
            AuditLog.event_name == event_name,
            AuditLog.details == details,
        )
        .limit(1)
    )
    if exists is None:
        db.add(
            AuditLog(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                event_name=event_name,
                details=details,
            )
        )
        db.commit()


def _ensure_ai_feedback(db: Session, *, workspace_id: int, user_id: int) -> None:
    snapshots = list(
        db.scalars(
            select(AIAnalysisSnapshot)
            .join(Lead, AIAnalysisSnapshot.lead_id == Lead.id)
            .where(Lead.workspace_id == workspace_id)
            .order_by(AIAnalysisSnapshot.id)
        )
    )
    ratings = ["useful", "useful", "not_useful"]
    for index, snapshot in enumerate(snapshots[:3]):
        exists = db.scalar(
            select(AIFeedback.id)
            .where(
                AIFeedback.workspace_id == workspace_id,
                AIFeedback.ai_analysis_snapshot_id == snapshot.id,
                AIFeedback.user_id == user_id,
            )
            .limit(1)
        )
        if exists is not None:
            continue
        correction = None
        if ratings[index] == "not_useful":
            correction = "Demo reviewer flagged this as needing clearer source attribution."
        db.add(
            AIFeedback(
                workspace_id=workspace_id,
                ai_analysis_snapshot_id=snapshot.id,
                user_id=user_id,
                rating=ratings[index],
                correction_text=correction,
                created_at=snapshot.created_at + timedelta(minutes=20 + index),
            )
        )
    db.commit()


def _ensure_outreach_status_mix(db: Session, *, workspace_id: int) -> None:
    messages = list(
        db.scalars(
            select(OutreachMessage)
            .join(Lead, OutreachMessage.lead_id == Lead.id)
            .where(Lead.workspace_id == workspace_id)
            .order_by(OutreachMessage.id)
        )
    )
    for index, message in enumerate(messages):
        message.outreach_status = "sent" if index == 0 else "draft"
        message.updated_at = datetime.now(tz=UTC)
        db.add(message)
    db.commit()


def _ensure_platform_and_workspace_records(db: Session) -> tuple[Workspace, Workspace, User, User]:
    ensure_default_roles(db)
    platform_workspace = _ensure_workspace(
        db,
        public_id=PLATFORM_WORKSPACE_PUBLIC_ID,
        name="LeadScope Platform Operations",
        slug="platform-ops",
        status="active",
    )
    disabled_workspace = _ensure_workspace(
        db,
        public_id=DISABLED_WORKSPACE_PUBLIC_ID,
        name="Disabled Demo Workspace",
        slug="disabled-demo-workspace",
        status="disabled",
    )
    platform_admin = _ensure_demo_user(
        db,
        workspace_id=platform_workspace.id,
        email=DEMO_PLATFORM_EMAIL,
        full_name="Platform Admin",
        password=DEMO_PLATFORM_PASSWORD,
        role="platform_admin",
    )
    disabled_owner = _ensure_demo_user(
        db,
        workspace_id=disabled_workspace.id,
        email=DISABLED_OWNER_EMAIL,
        full_name="Disabled Workspace Owner",
        password=DISABLED_OWNER_PASSWORD,
        role="account_owner",
    )
    platform_workspace.owner_user_id = platform_admin.id
    disabled_workspace.owner_user_id = disabled_owner.id
    db.add_all([platform_workspace, disabled_workspace])
    db.commit()
    return platform_workspace, disabled_workspace, platform_admin, disabled_owner


def _ensure_billing_and_usage(
    db: Session,
    *,
    active_workspace: Workspace,
    disabled_workspace: Workspace,
) -> None:
    growth_plan = _ensure_plan(
        db,
        code="growth",
        name="Growth",
        monthly_price=Decimal("99.00"),
        yearly_price=Decimal("948.00"),
        limits_json={
            "searches_per_month": 250,
            "exports_per_month": 100,
            "ai_scoring_runs_per_month": 500,
            "outreach_generations_per_month": 700,
            "max_team_users": 10,
        },
    )
    platform_plan = _ensure_plan(
        db,
        code="platform_demo",
        name="Platform Demo",
        monthly_price=Decimal("249.00"),
        yearly_price=Decimal("2388.00"),
        limits_json={
            "searches_per_month": 1000,
            "exports_per_month": 500,
            "ai_scoring_runs_per_month": 2000,
            "outreach_generations_per_month": 3000,
            "max_team_users": 30,
        },
    )
    base_time = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)
    active_subscription = _ensure_subscription(
        db,
        public_id="sub_demo_active",
        workspace_id=active_workspace.id,
        plan_id=growth_plan.id,
        status="active",
        billing_cycle="monthly",
        started_at=base_time,
        renews_at=base_time + timedelta(days=30),
    )
    disabled_subscription = _ensure_subscription(
        db,
        public_id="sub_demo_disabled",
        workspace_id=disabled_workspace.id,
        plan_id=platform_plan.id,
        status="past_due",
        billing_cycle="monthly",
        started_at=base_time - timedelta(days=60),
        renews_at=base_time - timedelta(days=1),
    )
    _ensure_invoice(
        db,
        public_id="inv_demo_active_apr",
        workspace_id=active_workspace.id,
        subscription_id=active_subscription.id,
        amount=Decimal("99.00"),
        status="paid",
        issued_at=base_time,
        item_description="Growth plan - April 2026",
        payment_status="succeeded",
        payment_result="success",
    )
    _ensure_invoice(
        db,
        public_id="inv_demo_disabled",
        workspace_id=disabled_workspace.id,
        subscription_id=disabled_subscription.id,
        amount=Decimal("249.00"),
        status="open",
        issued_at=base_time - timedelta(days=31),
        item_description="Platform Demo plan - overdue workspace verification",
        payment_status="failed",
        payment_result="failure",
        payment_error="Demo-only failed payment for platform admin billing review.",
    )

    period_start = datetime(2026, 4, 1, tzinfo=UTC)
    period_end = datetime(2026, 5, 1, tzinfo=UTC)
    for metric_key, value in {
        "searches_per_month": 17,
        "exports_per_month": 4,
        "ai_scoring_runs_per_month": 38,
        "outreach_generations_per_month": 12,
        "max_team_users": 3,
    }.items():
        _ensure_usage_counter(
            db,
            workspace_id=active_workspace.id,
            metric_key=metric_key,
            current_value=value,
            period_start=period_start,
            period_end=period_end,
        )
    _ensure_usage_counter(
        db,
        workspace_id=disabled_workspace.id,
        metric_key="searches_per_month",
        current_value=0,
        period_start=period_start,
        period_end=period_end,
    )


def _count_for_workspace(db: Session, model: type[object], workspace_id: int) -> int:
    return int(
        db.scalar(select(func.count()).select_from(model).where(model.workspace_id == workspace_id))
        or 0
    )


def _build_summary(
    db: Session,
    *,
    platform_workspace: Workspace,
    active_workspace: Workspace,
    disabled_workspace: Workspace,
    platform_admin: User,
    owner: User,
    manager: User,
    member: User,
    disabled_owner: User,
) -> DemoSeedSummary:
    workspace_id = active_workspace.id
    return DemoSeedSummary(
        platform_workspace=platform_workspace,
        active_workspace=active_workspace,
        disabled_workspace=disabled_workspace,
        platform_admin=platform_admin,
        owner=owner,
        manager=manager,
        member=member,
        disabled_owner=disabled_owner,
        leads_count=_count_for_workspace(db, Lead, workspace_id),
        signals_count=_count_for_workspace(db, LeadSignal, workspace_id),
        signal_scores_count=_count_for_workspace(db, LeadSignalScore, workspace_id),
        icp_profiles_count=_count_for_workspace(db, IcpProfile, workspace_id),
        icp_matches_count=_count_for_workspace(db, LeadIcpMatch, workspace_id),
        provider_fetches_count=_count_for_workspace(db, ProviderFetch, workspace_id),
        provider_facts_count=_count_for_workspace(db, ProviderNormalizedFact, workspace_id),
        provider_errors_count=int(
            db.scalar(
                select(func.count())
                .select_from(ProviderFetch)
                .where(
                    ProviderFetch.workspace_id == workspace_id,
                    ProviderFetch.status != "ok",
                )
            )
            or 0
        ),
        scoring_breakdowns_count=int(
            db.scalar(
                select(func.count())
                .select_from(ScoreBreakdown)
                .join(LeadScore, ScoreBreakdown.lead_score_id == LeadScore.id)
                .join(Lead, LeadScore.lead_id == Lead.id)
                .where(Lead.workspace_id == workspace_id)
            )
            or 0
        ),
        ai_snapshots_count=int(
            db.scalar(
                select(func.count())
                .select_from(AIAnalysisSnapshot)
                .join(Lead, AIAnalysisSnapshot.lead_id == Lead.id)
                .where(Lead.workspace_id == workspace_id)
            )
            or 0
        ),
        ai_evidence_count=int(
            db.scalar(
                select(func.count())
                .select_from(AIAnalysisEvidence)
                .join(
                    AIAnalysisSnapshot,
                    AIAnalysisEvidence.ai_analysis_snapshot_id == AIAnalysisSnapshot.id,
                )
                .join(Lead, AIAnalysisSnapshot.lead_id == Lead.id)
                .where(Lead.workspace_id == workspace_id)
            )
            or 0
        ),
        ai_feedback_count=_count_for_workspace(db, AIFeedback, workspace_id),
        outreach_drafts_count=int(
            db.scalar(
                select(func.count())
                .select_from(OutreachMessage)
                .join(Lead, OutreachMessage.lead_id == Lead.id)
                .where(
                    Lead.workspace_id == workspace_id,
                    OutreachMessage.outreach_status == "draft",
                )
            )
            or 0
        ),
        outreach_sent_count=int(
            db.scalar(
                select(func.count())
                .select_from(OutreachMessage)
                .join(Lead, OutreachMessage.lead_id == Lead.id)
                .where(
                    Lead.workspace_id == workspace_id,
                    OutreachMessage.outreach_status == "sent",
                )
            )
            or 0
        ),
        usage_counters_count=_count_for_workspace(db, UsageCounter, workspace_id),
    )


def seed_demo_full() -> DemoSeedSummary:
    settings = get_settings()
    if settings.is_production:
        raise RuntimeError("Full demo seeding is blocked when APP_ENV=production.")

    with SessionLocal() as db:
        _seed_demo_workspace(db)
        active_workspace = db.scalar(
            select(Workspace).where(Workspace.public_id == ACTIVE_WORKSPACE_PUBLIC_ID)
        )
        if active_workspace is None:
            raise RuntimeError("Expected the base demo workspace to exist after seed.py ran.")
        active_workspace.status = "active"
        active_workspace.updated_at = datetime.now(tz=UTC)
        db.add(active_workspace)
        db.commit()
        db.refresh(active_workspace)

        owner = db.scalar(select(User).where(User.email == DEMO_OWNER_EMAIL))
        manager = db.scalar(select(User).where(User.email == DEMO_MANAGER_EMAIL))
        member = db.scalar(select(User).where(User.email == DEMO_MEMBER_EMAIL))
        if owner is None or manager is None or member is None:
            raise RuntimeError("Expected base demo users were not seeded.")

        platform_workspace, disabled_workspace, platform_admin, disabled_owner = (
            _ensure_platform_and_workspace_records(db)
        )
        ensure_base_workspace_configuration(
            db,
            workspace_id=platform_workspace.id,
            admin_id=platform_admin.id,
        )
        ensure_base_workspace_configuration(
            db,
            workspace_id=disabled_workspace.id,
            admin_id=disabled_owner.id,
        )
        _ensure_billing_and_usage(
            db,
            active_workspace=active_workspace,
            disabled_workspace=disabled_workspace,
        )
        _ensure_ai_feedback(db, workspace_id=active_workspace.id, user_id=owner.id)
        _ensure_outreach_status_mix(db, workspace_id=active_workspace.id)
        _ensure_audit_log(
            db,
            workspace_id=active_workspace.id,
            actor_user_id=platform_admin.id,
            event_name="platform_admin.workspace_enabled",
            details="Demo platform admin verified active workspace access.",
        )
        _ensure_audit_log(
            db,
            workspace_id=disabled_workspace.id,
            actor_user_id=platform_admin.id,
            event_name="platform_admin.workspace_disabled",
            details="Demo disabled workspace is available for access-block verification.",
        )
        return _build_summary(
            db,
            platform_workspace=platform_workspace,
            active_workspace=active_workspace,
            disabled_workspace=disabled_workspace,
            platform_admin=platform_admin,
            owner=owner,
            manager=manager,
            member=member,
            disabled_owner=disabled_owner,
        )


def _print_summary(summary: DemoSeedSummary) -> None:
    print("Full demo seed completed.")
    print("")
    print("Demo credentials:")
    print(f"- Platform admin: {DEMO_PLATFORM_EMAIL} / {DEMO_PLATFORM_PASSWORD}")
    print(f"- Workspace owner: {DEMO_OWNER_EMAIL} / {DEMO_OWNER_PASSWORD}")
    print(f"- Workspace manager: {DEMO_MANAGER_EMAIL} / {DEMO_MANAGER_PASSWORD}")
    print(f"- Workspace member: {DEMO_MEMBER_EMAIL} / {DEMO_MEMBER_PASSWORD}")
    print(f"- Disabled workspace owner: {DISABLED_OWNER_EMAIL} / {DISABLED_OWNER_PASSWORD}")
    print("")
    print("Workspaces:")
    print(
        "- Platform ops: "
        f"{summary.platform_workspace.public_id} / {summary.platform_workspace.slug} "
        f"({summary.platform_workspace.status})"
    )
    print(
        "- Active demo: "
        f"{summary.active_workspace.public_id} / {summary.active_workspace.slug} "
        f"({summary.active_workspace.status})"
    )
    print(
        "- Disabled demo: "
        f"{summary.disabled_workspace.public_id} / {summary.disabled_workspace.slug} "
        f"({summary.disabled_workspace.status})"
    )
    print("")
    print("Seeded active-workspace records:")
    print(f"- Leads: {summary.leads_count}")
    print(f"- Lead signals: {summary.signals_count}")
    print(f"- Lead signal scores: {summary.signal_scores_count}")
    print(f"- ICP profiles: {summary.icp_profiles_count}")
    print(f"- ICP matches: {summary.icp_matches_count}")
    print(f"- Provider fetches: {summary.provider_fetches_count}")
    print(f"- Provider normalized facts: {summary.provider_facts_count}")
    print(f"- Provider errors: {summary.provider_errors_count}")
    print(f"- Score breakdown rows: {summary.scoring_breakdowns_count}")
    print(f"- AI analysis snapshots: {summary.ai_snapshots_count}")
    print(f"- AI evidence rows: {summary.ai_evidence_count}")
    print(f"- AI feedback rows: {summary.ai_feedback_count}")
    print(f"- Outreach drafts: {summary.outreach_drafts_count}")
    print(f"- Outreach sent: {summary.outreach_sent_count}")
    print(f"- Usage counters: {summary.usage_counters_count}")


def main() -> None:
    if "--migrate" in sys.argv:
        run_migrations()
    _print_summary(seed_demo_full())


if __name__ == "__main__":
    main()
