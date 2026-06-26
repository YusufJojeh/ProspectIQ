from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, Field, StringConstraints

from app.modules.leads.schemas import LeadResponse


class DealStatus(StrEnum):
    OPEN = "open"
    WON = "won"
    LOST = "lost"
    ARCHIVED = "archived"


class StageType(StrEnum):
    OPEN = "open"
    WON = "won"
    LOST = "lost"


class ActivityType(StrEnum):
    NOTE = "note"
    CALL = "call"
    MEETING = "meeting"
    EMAIL = "email"
    FOLLOW_UP = "follow_up"
    STATUS_CHANGE = "status_change"


class PipelineCreateRequest(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=160)]
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None


class PipelineUpdateRequest(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=160)] | None = None
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None
    is_default: bool | None = None


class StageCreateRequest(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
    probability: int = Field(ge=0, le=100)
    color: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=32)] = "slate"
    stage_type: StageType = StageType.OPEN


class StageUpdateRequest(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)] | None = None
    probability: int | None = Field(default=None, ge=0, le=100)
    color: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=32)] | None = None
    stage_type: StageType | None = None


class StageReorderRequest(BaseModel):
    stage_ids: list[str] = Field(min_length=1, max_length=50)


class StageResponse(BaseModel):
    public_id: str
    name: str
    position: int
    probability: int
    color: str
    stage_type: StageType
    deal_count: int = 0
    total_value: float = 0
    created_at: datetime
    updated_at: datetime


class PipelineResponse(BaseModel):
    public_id: str
    name: str
    description: str | None
    is_default: bool
    stages: list[StageResponse]
    created_at: datetime
    updated_at: datetime


class PipelineListResponse(BaseModel):
    items: list[PipelineResponse]


class DealCreateRequest(BaseModel):
    lead_id: str
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=180)] | None = None
    pipeline_id: str | None = None
    stage_id: str | None = None
    campaign_id: str | None = None
    owner_user_id: str | None = None
    value_amount: float | None = Field(default=None, ge=0)
    currency: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=8)] = "USD"
    probability: int | None = Field(default=None, ge=0, le=100)
    expected_close_date: datetime | None = None
    next_follow_up_at: datetime | None = None
    allow_duplicate_open: bool = False


class DealUpdateRequest(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=180)] | None = None
    stage_id: str | None = None
    owner_user_id: str | None = None
    value_amount: float | None = Field(default=None, ge=0)
    currency: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=8)] | None = None
    probability: int | None = Field(default=None, ge=0, le=100)
    status: DealStatus | None = None
    lost_reason: Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] | None = None
    expected_close_date: datetime | None = None
    next_follow_up_at: datetime | None = None


class DealMoveRequest(BaseModel):
    stage_id: str


class DealLostRequest(BaseModel):
    lost_reason: Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] | None = None


class ActivityCreateRequest(BaseModel):
    activity_type: ActivityType = ActivityType.NOTE
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=180)]
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)] | None = None
    due_at: datetime | None = None
    metadata: dict[str, Any] | None = None


class ActivityUpdateRequest(BaseModel):
    activity_type: ActivityType | None = None
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=180)] | None = None
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)] | None = None
    due_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] | None = None


class ActivityResponse(BaseModel):
    public_id: str
    deal_id: str
    activity_type: ActivityType
    title: str
    note: str | None
    due_at: datetime | None
    completed_at: datetime | None
    actor_user_id: str | None
    actor_full_name: str | None
    metadata: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class DealResponse(BaseModel):
    public_id: str
    title: str
    pipeline_id: str
    pipeline_name: str
    stage_id: str
    stage_name: str
    stage_probability: int
    lead: LeadResponse
    campaign_id: str | None
    campaign_name: str | None
    owner_user_id: str | None
    owner_full_name: str | None
    value_amount: float | None
    currency: str
    probability: int
    status: DealStatus
    lost_reason: str | None
    expected_close_date: datetime | None
    next_follow_up_at: datetime | None
    last_activity_at: datetime | None
    next_activity: ActivityResponse | None
    overdue_activity_count: int
    created_at: datetime
    updated_at: datetime


class DealListResponse(BaseModel):
    items: list[DealResponse]


class DealDetailResponse(DealResponse):
    activities: list[ActivityResponse]


class DealActionResponse(BaseModel):
    status: str
    deal: DealResponse | None = None


class CampaignCreateDealsResponse(BaseModel):
    created_count: int
    skipped_count: int
    deals: list[DealResponse]
    skipped_lead_ids: list[str]


class CreateDealsFromSourceRequest(BaseModel):
    allow_duplicate_open: bool = False
