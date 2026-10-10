from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ResearchDepth = Literal["quick", "standard", "deep"]
ResearchProviderName = Literal["tavily", "serpapi", "apify"]
ResearchMode = Literal["planned", "agentic"]


class ResearchStep(BaseModel):
    provider: ResearchProviderName
    mode: str
    reason: str


class ResearchPlan(BaseModel):
    depth: ResearchDepth
    steps: list[ResearchStep] = Field(default_factory=list)


class ContradictionValue(BaseModel):
    value: str
    provider: str
    source_url: str | None = None
    confidence: float


class ContradictionSummary(BaseModel):
    claim_type: str
    values: list[ContradictionValue]


class ResearchRunResult(BaseModel):
    depth: ResearchDepth
    mode: ResearchMode = "planned"
    providers_used: list[str] = Field(default_factory=list)
    steps_executed: int = 0
    facts_created: int = 0
    contradictions: list[ContradictionSummary] = Field(default_factory=list)
    status: str
    message: str
    last_provider_fetch_public_id: str | None = None
    tool_calls_made: int = 0


class ResearchHistoryChange(BaseModel):
    #: ResearchChangeEvent public id; citable as evidence of the change.
    change_id: str | None = None
    claim_type: str
    change_type: str
    before: str | None
    after: str | None
    significance: float
    explanation: str | None


class ResearchHistoryItem(BaseModel):
    run_id: str
    mode: str
    depth: str
    started_at: datetime
    completed_at: datetime
    status: str
    evidence_confidence: float
    research_coverage: float
    score_before: float | None = None
    score_after: float | None = None
    changes: list[ResearchHistoryChange] = Field(default_factory=list)


class ResearchHistoryPagination(BaseModel):
    page: int
    per_page: int
    total: int


class ResearchHistoryResponse(BaseModel):
    lead_id: str
    items: list[ResearchHistoryItem] = Field(default_factory=list)
    pagination: ResearchHistoryPagination
