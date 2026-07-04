from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class LeadSignalResponse(BaseModel):
    public_id: str
    signal_type: str
    signal_strength: float
    evidence_text: str
    source_url: str | None
    detected_at: datetime


class LeadSignalScoreResponse(BaseModel):
    signal_type: str
    score: float
    confidence: float
    evidence_count: int
    calculated_at: datetime


class LeadSignalsResponse(BaseModel):
    lead_id: str
    items: list[LeadSignalResponse]
    scores: list[LeadSignalScoreResponse]
