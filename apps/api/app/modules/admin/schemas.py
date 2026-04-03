from __future__ import annotations

from pydantic import BaseModel, Field

from app.modules.scoring.schemas import (
    ActiveScoringConfigResponse,
    ScoringConfigVersionCreateRequest,
    ScoringConfigVersionListResponse,
    ScoringConfigVersionResponse,
)


class ProviderSettingsResponse(BaseModel):
    hl: str
    gl: str
    google_domain: str
    enrich_top_n: int


class ProviderSettingsUpdateRequest(BaseModel):
    hl: str | None = Field(default=None, max_length=16)
    gl: str | None = Field(default=None, max_length=16)
    google_domain: str | None = Field(default=None, max_length=64)
    enrich_top_n: int | None = Field(default=None, ge=0, le=100)


__all__ = [
    "ActiveScoringConfigResponse",
    "ScoringConfigVersionCreateRequest",
    "ScoringConfigVersionListResponse",
    "ScoringConfigVersionResponse",
    "ProviderSettingsResponse",
    "ProviderSettingsUpdateRequest",
]
