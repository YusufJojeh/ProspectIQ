from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.policies import get_current_user
from app.modules.billing.schemas import (
    BillingSimulationRequest,
    InvoiceListResponse,
    InvoiceResponse,
    PlanListResponse,
    SubscriptionChangeRequest,
    SubscriptionResponse,
    UsageSummaryResponse,
)
from app.modules.billing.service import BillingService
from app.modules.users.models import User

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


@router.get("/plans", response_model=PlanListResponse)
def list_plans(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> PlanListResponse:
    return BillingService().list_plans(db)


@router.get("/subscription", response_model=SubscriptionResponse)
def get_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SubscriptionResponse:
    return BillingService().get_subscription(db, workspace_id=current_user.workspace_id)


@router.get("/invoices", response_model=InvoiceListResponse)
def list_invoices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InvoiceListResponse:
    return BillingService().list_invoices(db, workspace_id=current_user.workspace_id)


@router.get("/usage", response_model=UsageSummaryResponse)
def get_usage(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UsageSummaryResponse:
    return BillingService().get_usage_summary(db, workspace_id=current_user.workspace_id)


@router.post("/subscription/change", response_model=SubscriptionResponse)
def change_subscription(
    payload: SubscriptionChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SubscriptionResponse:
    return BillingService().change_subscription(
        db,
        workspace_id=current_user.workspace_id,
        payload=payload,
        actor=current_user,
    )


@router.post("/subscription/cancel", response_model=SubscriptionResponse)
def cancel_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SubscriptionResponse:
    return BillingService().cancel_subscription(db, workspace_id=current_user.workspace_id, actor=current_user)


@router.post("/subscription/renew", response_model=SubscriptionResponse)
def renew_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SubscriptionResponse:
    return BillingService().renew_subscription(db, workspace_id=current_user.workspace_id, actor=current_user)


@router.post("/invoices/mark-paid", response_model=InvoiceResponse)
def mark_invoice_paid(
    payload: BillingSimulationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InvoiceResponse:
    assert payload.invoice_public_id is not None
    return BillingService().mark_invoice_paid(
        db,
        workspace_id=current_user.workspace_id,
        invoice_public_id=payload.invoice_public_id,
        actor=current_user,
    )


@router.post("/invoices/simulate-failure", response_model=InvoiceResponse)
def simulate_invoice_failure(
    payload: BillingSimulationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InvoiceResponse:
    assert payload.invoice_public_id is not None
    return BillingService().simulate_payment_failure(
        db,
        workspace_id=current_user.workspace_id,
        invoice_public_id=payload.invoice_public_id,
        actor=current_user,
        error_message=payload.error_message,
    )
