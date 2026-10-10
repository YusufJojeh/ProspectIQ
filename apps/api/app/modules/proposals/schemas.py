from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.modules.proposals.documents import MAX_AMOUNT_MINOR

ProposalStatus = Literal["draft", "ready", "sent", "accepted", "declined"]
ProposalLanguage = Literal["en", "ar"]
ProposalDecision = Literal["accepted", "declined"]

_Currency = Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Z]{3}$")]


class MilestoneInput(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=600)] = ""
    #: Minor units (cents). None means "not priced yet".
    amount_minor: Annotated[int, Field(ge=0, le=MAX_AMOUNT_MINOR)] | None = None


class MilestoneResponse(BaseModel):
    title: str
    description: str
    amount_minor: int | None
    share_pct: float | None


class ProposalTotals(BaseModel):
    total_minor: int
    deposit_minor: int
    remaining_minor: int


class ProposalReadiness(BaseModel):
    ready: bool
    issues: list[str]


class BrandResponse(BaseModel):
    key: str
    name: str
    tagline: str
    mark: str
    mark_shape: str
    number_prefix: str
    signer_label: str
    client_signer_label: str
    footer_contact: str
    paper: str
    ink: str
    muted: str
    line: str
    accent: str
    accent_secondary: str
    background: str
    radius_px: int
    default_currency: str
    validity_days: int


class BrandListResponse(BaseModel):
    items: list[BrandResponse]


class ProposalCreateRequest(BaseModel):
    lead_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)]
    brand_key: str
    language: ProposalLanguage = "en"


class ProposalUpdateRequest(BaseModel):
    """Partial update. A field left out is unchanged; `null` clears only the
    optional contact fields."""

    brand_key: str | None = None
    language: ProposalLanguage | None = None
    title: Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] | None = None
    client_company: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] | None
    ) = None
    client_contact_name: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] | None
    ) = None
    client_email: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=320)] | None
    ) = None
    client_location: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] | None
    ) = None
    currency: _Currency | None = None
    issue_date: date | None = None
    valid_until: date | None = None
    outcome: Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)] | None = None
    milestones: Annotated[list[MilestoneInput], Field(max_length=12)] | None = None
    commercial_notes: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None
    ) = None
    validity_notes: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None
    ) = None
    sender_contact: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] | None
    ) = None

    @model_validator(mode="after")
    def _dates_in_order(self) -> ProposalUpdateRequest:
        if (
            self.issue_date is not None
            and self.valid_until is not None
            and self.valid_until <= self.issue_date
        ):
            raise ValueError("valid_until must be after issue_date")
        return self


class ProposalDecisionRequest(BaseModel):
    decision: ProposalDecision


class ProposalResponse(BaseModel):
    public_id: str
    number: str
    status: ProposalStatus
    lead_id: str
    lead_company_name: str
    brand: BrandResponse
    language: ProposalLanguage
    title: str
    client_company: str
    client_contact_name: str | None
    client_email: str | None
    client_location: str | None
    currency: str
    issue_date: date
    valid_until: date
    outcome: str
    milestones: list[MilestoneResponse]
    commercial_notes: str
    validity_notes: str
    sender_contact: str
    pricing_basis: str | None
    source_agent_run_id: str | None
    totals: ProposalTotals
    readiness: ProposalReadiness
    sent_at: datetime | None
    decided_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ProposalSummary(BaseModel):
    public_id: str
    number: str
    status: ProposalStatus
    lead_id: str
    lead_company_name: str
    brand_key: str
    title: str
    client_company: str
    currency: str
    total_minor: int
    valid_until: date
    ready: bool
    updated_at: datetime


class ProposalListResponse(BaseModel):
    items: list[ProposalSummary]
