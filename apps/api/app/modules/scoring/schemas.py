from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.shared.enums.jobs import LeadScoreBand


class ScoreBreakdownItem(BaseModel):
    key: str
    label: str
    weight: float
    contribution: float
    reason: str


class ScoringWeights(BaseModel):
    local_trust: float = Field(default=0.25, ge=0, le=1)
    website_presence: float = Field(default=0.25, ge=0, le=1)
    search_visibility: float = Field(default=0.2, ge=0, le=1)
    opportunity: float = Field(default=0.2, ge=0, le=1)
    data_confidence: float = Field(default=0.1, ge=0, le=1)


class ScoringThresholds(BaseModel):
    high_min: float = Field(default=75, ge=0, le=100)
    medium_min: float = Field(default=55, ge=0, le=100)
    low_min: float = Field(default=35, ge=0, le=100)
    confidence_min: float = Field(default=0.45, ge=0, le=1)


class LeadScoreResult(BaseModel):
    total_score: float
    band: LeadScoreBand
    qualified: bool
    breakdown: list[ScoreBreakdownItem]


class ScoringConfigVersionCreateRequest(BaseModel):
    weights: ScoringWeights
    thresholds: ScoringThresholds
    note: str | None = Field(default=None, max_length=255)


class ScoringConfigVersionResponse(BaseModel):
    public_id: str
    weights: ScoringWeights
    thresholds: ScoringThresholds
    note: str | None
    created_at: datetime
    created_by_user_public_id: str


class ActiveScoringConfigResponse(BaseModel):
    active_version: ScoringConfigVersionResponse


class ScoringConfigVersionListResponse(BaseModel):
    items: list[ScoringConfigVersionResponse]
