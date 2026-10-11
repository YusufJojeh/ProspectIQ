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


_HexColor = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^#[0-9A-Fa-f]{6}$")]
MarkShape = Literal["square", "hex", "circle"]
FontStyle = Literal["sans", "serif"]

#: ~300 KB of image, base64-encoded. PNG/JPEG/WebP only: an SVG logo could
#: carry script, and the logo is embedded in a document clients receive.
MAX_LOGO_DATA_URL_LENGTH = 400_000
_LOGO_PATTERN = r"^data:image/(png|jpeg|webp);base64,[A-Za-z0-9+/]+={0,2}$"


class BrandMilestone(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=600)] = ""


class BrandFields(BaseModel):
    """Everything a workspace controls about how its proposals look and start."""

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    tagline: Annotated[str, StringConstraints(strip_whitespace=True, max_length=160)] = ""
    mark: Annotated[str, StringConstraints(strip_whitespace=True, max_length=4)] = ""
    mark_shape: MarkShape = "circle"
    font_style: FontStyle = "sans"
    logo_data_url: (
        Annotated[
            str,
            StringConstraints(max_length=MAX_LOGO_DATA_URL_LENGTH, pattern=_LOGO_PATTERN),
        ]
        | None
    ) = None
    number_prefix: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, to_upper=True, pattern=r"^[A-Za-z0-9]{1,8}(-[A-Za-z0-9]{1,6})?$"
        ),
    ]
    signer_label: Annotated[str, StringConstraints(strip_whitespace=True, max_length=160)] = ""
    client_signer_label: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=160)]
    ) = ""
    footer_contact: Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] = ""
    paper: _HexColor
    ink: _HexColor
    muted: _HexColor
    line: _HexColor
    accent: _HexColor
    accent_secondary: _HexColor
    background: _HexColor
    radius_px: Annotated[int, Field(ge=0, le=24)] = 8
    default_currency: _Currency = "USD"
    validity_days: Annotated[int, Field(ge=1, le=365)] = 30
    default_outcome: Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)] = ""
    default_commercial_notes: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]
    ) = ""
    default_validity_notes: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]
    ) = ""
    default_milestones: Annotated[list[BrandMilestone], Field(max_length=12)] = []


class BrandCreateRequest(BrandFields):
    is_default: bool = False


class BrandUpdateRequest(BaseModel):
    """Partial update; a field left out is unchanged. `logo_data_url: null`
    removes the logo."""

    name: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
        | None
    ) = None
    tagline: Annotated[str, StringConstraints(strip_whitespace=True, max_length=160)] | None = None
    mark: Annotated[str, StringConstraints(strip_whitespace=True, max_length=4)] | None = None
    mark_shape: MarkShape | None = None
    font_style: FontStyle | None = None
    logo_data_url: (
        Annotated[
            str,
            StringConstraints(max_length=MAX_LOGO_DATA_URL_LENGTH, pattern=_LOGO_PATTERN),
        ]
        | None
    ) = None
    number_prefix: (
        Annotated[
            str,
            StringConstraints(
                strip_whitespace=True, to_upper=True, pattern=r"^[A-Za-z0-9]{1,8}(-[A-Za-z0-9]{1,6})?$"
            ),
        ]
        | None
    ) = None
    signer_label: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=160)] | None
    ) = None
    client_signer_label: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=160)] | None
    ) = None
    footer_contact: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] | None
    ) = None
    paper: _HexColor | None = None
    ink: _HexColor | None = None
    muted: _HexColor | None = None
    line: _HexColor | None = None
    accent: _HexColor | None = None
    accent_secondary: _HexColor | None = None
    background: _HexColor | None = None
    radius_px: Annotated[int, Field(ge=0, le=24)] | None = None
    default_currency: _Currency | None = None
    validity_days: Annotated[int, Field(ge=1, le=365)] | None = None
    default_outcome: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)] | None
    ) = None
    default_commercial_notes: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None
    ) = None
    default_validity_notes: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None
    ) = None
    default_milestones: Annotated[list[BrandMilestone], Field(max_length=12)] | None = None
    archived: bool | None = None


class BrandResponse(BrandFields):
    """A workspace brand. Also the shape of a sent proposal's frozen brand."""

    public_id: str
    is_default: bool = False
    archived: bool = False


class BrandListResponse(BaseModel):
    items: list[BrandResponse]


class BrandTemplateResponse(BaseModel):
    key: str
    values: BrandFields


class BrandTemplateListResponse(BaseModel):
    items: list[BrandTemplateResponse]


class ProposalCreateRequest(BaseModel):
    lead_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)]
    #: A workspace brand's public id; omitted means the workspace default.
    brand_id: Annotated[str, StringConstraints(strip_whitespace=True, max_length=32)] | None = None
    language: ProposalLanguage = "en"


class ProposalUpdateRequest(BaseModel):
    """Partial update. A field left out is unchanged; `null` clears only the
    optional contact fields."""

    brand_id: Annotated[str, StringConstraints(strip_whitespace=True, max_length=32)] | None = None
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
    brand_id: str
    brand_name: str
    title: str
    client_company: str
    currency: str
    total_minor: int
    valid_until: date
    ready: bool
    updated_at: datetime


class ProposalListResponse(BaseModel):
    items: list[ProposalSummary]


AuditFindingKey = Literal["website", "rating", "reviews", "phone", "email", "social"]
AuditFindingStatus = Literal["good", "improve", "missing"]


class AuditFinding(BaseModel):
    key: AuditFindingKey
    status: AuditFindingStatus
    #: Numbers the sentence quotes (rating, counts, peer medians); the
    #: document words them in its own language.
    values: dict[str, float | int]


class AuditBenchmark(BaseModel):
    peer_count: int
    median_rating: float | None
    median_reviews: int
    website_pct: int


class AuditEvidence(BaseModel):
    signal_type: str
    text: str
    source_url: str | None


class LeadAuditResponse(BaseModel):
    lead_id: str
    company_name: str
    category: str | None
    city: str | None
    website_url: str | None
    email: str | None
    generated_on: date
    findings: list[AuditFinding]
    benchmark: AuditBenchmark | None
    evidence: list[AuditEvidence]
