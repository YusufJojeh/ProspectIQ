from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.modules.leads.schemas import LeadResponse
from app.modules.outreach.schemas import OutreachDraftResponse


class CampaignStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class CampaignLeadStatus(StrEnum):
    ADDED = "added"
    DRAFTED = "drafted"
    READY = "ready"
    SKIPPED = "skipped"
    REMOVED = "removed"


class SequenceChannel(StrEnum):
    EMAIL = "email"
    LINKEDIN = "linkedin"
    WHATSAPP_NOTE = "whatsapp_note"


class CampaignCreateRequest(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=160)]
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None
    icp_profile_id: str | None = None


class CampaignUpdateRequest(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=160)] | None = None
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None
    status: CampaignStatus | None = None


class CampaignResponse(BaseModel):
    public_id: str
    name: str
    description: str | None
    icp_profile_id: str | None
    status: CampaignStatus
    lead_count: int
    sequence_steps_count: int
    created_at: datetime
    updated_at: datetime


class CampaignListResponse(BaseModel):
    items: list[CampaignResponse]


class CampaignLeadAddRequest(BaseModel):
    lead_ids: list[str] = Field(min_length=1, max_length=100)


class CampaignLeadResponse(BaseModel):
    lead: LeadResponse
    status: CampaignLeadStatus
    added_at: datetime


class SequenceStepResponse(BaseModel):
    public_id: str
    step_order: int
    channel: SequenceChannel
    delay_days: int
    tone: str
    language: str
    template_text: str
    created_at: datetime
    updated_at: datetime


class SequenceStepUpdateRequest(BaseModel):
    channel: SequenceChannel | None = None
    delay_days: int | None = Field(default=None, ge=0, le=365)
    tone: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=32)] | None = None
    language: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=8)] | None = None
    template_text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=8000)] | None = None

    @field_validator("tone")
    @classmethod
    def normalize_tone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        allowed = {"formal", "friendly", "consultative", "short_pitch"}
        if value not in allowed:
            raise ValueError(f"tone must be one of: {', '.join(sorted(allowed))}")
        return value


class OutreachEventResponse(BaseModel):
    public_id: str
    event_type: str
    occurred_at: datetime
    lead_id: str | None
    outreach_message_id: str | None
    metadata: dict[str, Any] | None


class CampaignDetailResponse(CampaignResponse):
    leads: list[CampaignLeadResponse]
    sequence_steps: list[SequenceStepResponse]
    drafts: list[OutreachDraftResponse]
    events: list[OutreachEventResponse]


class CampaignGenerateDraftsResponse(BaseModel):
    created_count: int
    drafts: list[OutreachDraftResponse]


class CampaignActionResponse(BaseModel):
    status: str
