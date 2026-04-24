from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PlanResponse(BaseModel):
    code: str
    name: str
    monthly_price: float
    yearly_price: float
    limits: dict[str, int]
    is_active: bool


class PlanListResponse(BaseModel):
    items: list[PlanResponse]


class SubscriptionResponse(BaseModel):
    public_id: str
    plan_code: str
    plan_name: str
    status: str
    billing_cycle: str
    started_at: datetime
    ends_at: datetime | None = None
    renews_at: datetime | None = None
    canceled_at: datetime | None = None
    trial_ends_at: datetime | None = None
    simulated_payment_method: str = "Simulated card ending in 4242"


class InvoiceItemResponse(BaseModel):
    description: str
    amount: float
    quantity: int


class PaymentAttemptResponse(BaseModel):
    public_id: str
    status: str
    simulated_result: str
    attempted_at: datetime
    error_message: str | None = None


class InvoiceResponse(BaseModel):
    public_id: str
    amount: float
    currency: str
    status: str
    issued_at: datetime
    due_at: datetime | None = None
    paid_at: datetime | None = None
    items: list[InvoiceItemResponse] = Field(default_factory=list)
    payment_attempts: list[PaymentAttemptResponse] = Field(default_factory=list)


class InvoiceListResponse(BaseModel):
    items: list[InvoiceResponse]


class UsageMetricResponse(BaseModel):
    metric_key: str
    current_value: int
    limit_value: int | None = None
    period_start: datetime
    period_end: datetime


class UsageSummaryResponse(BaseModel):
    items: list[UsageMetricResponse]


class SubscriptionChangeRequest(BaseModel):
    plan_code: str
    billing_cycle: str = "monthly"


class BillingSimulationRequest(BaseModel):
    invoice_public_id: str | None = None
    error_message: str | None = None

