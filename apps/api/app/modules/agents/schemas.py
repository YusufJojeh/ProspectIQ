from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

AgentRunStatus = Literal[
    "queued",
    "running",
    "waiting_for_approval",
    "completed",
    "failed",
    "cancelled",
    "expired",
]
AgentActionStatus = Literal[
    "pending",
    "approved",
    "executing",
    "executed",
    "rejected",
    "expired",
    "failed",
    "cancelled",
]
AgentToolType = Literal["read", "research", "write_proposal", "action"]
AgentRiskLevel = Literal["low", "medium", "high", "blocked"]


AgentProfileKey = Literal["research", "sales_copilot", "read_only", "admin_assistant"]


class AgentRunCreateRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=2000)
    lead_id: str | None = None
    #: A profile only ever narrows what the run may do; the runtime resolves
    #: an unknown or missing value to the default rather than to "no limits".
    profile: AgentProfileKey = "research"


class AgentRunResponse(BaseModel):
    run_id: str
    status: AgentRunStatus
    profile: str = "research"
    stop_reason: str | None = None
    lead_id: str | None
    goal: str
    step_count: int
    tool_call_count: int
    external_search_count: int
    crawl_count: int
    write_proposal_count: int
    final_answer: dict[str, Any] | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class AgentEventResponse(BaseModel):
    event_id: str
    seq: int
    event_type: str
    payload: dict[str, Any]
    created_at: datetime


class AgentEventListResponse(BaseModel):
    run_id: str
    events: list[AgentEventResponse] = Field(default_factory=list)


class AgentActionResponse(BaseModel):
    action_id: str
    run_id: str
    tool_name: str
    resource_type: str
    resource_id: str
    preview: dict[str, Any]
    risk_level: AgentRiskLevel
    status: AgentActionStatus
    result: dict[str, Any] | None
    failure_code: str | None
    failure_message: str | None
    expires_at: datetime
    approved_at: datetime | None
    executed_at: datetime | None
    created_at: datetime


class AgentActionListResponse(BaseModel):
    items: list[AgentActionResponse] = Field(default_factory=list)
    page: int
    per_page: int
    total: int


class AgentActionRejectRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class AgentFinalAnswer(BaseModel):
    """The mandatory structured shape every completed AgentRun.final_answer_json
    must validate against, server-side, independent of what the provider
    returned -- the model's raw output is never trusted verbatim.
    """

    answer: str
    lead_id: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    # Backend-owned: always overwritten from the Evidence Graph at completion,
    # so a model omitting it must not invalidate the rest of its answer.
    research_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_refs: list[str] = Field(default_factory=list)
    # Internal Sales Knowledge document ids, kept apart from lead evidence.
    # Server-filtered to documents actually selected during this run.
    knowledge_refs: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    completed_actions: list[str] = Field(default_factory=list)
    pending_actions: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)


__all__ = [
    "AgentActionListResponse",
    "AgentActionRejectRequest",
    "AgentActionResponse",
    "AgentActionStatus",
    "AgentEventListResponse",
    "AgentEventResponse",
    "AgentFinalAnswer",
    "AgentRiskLevel",
    "AgentRunCreateRequest",
    "AgentRunResponse",
    "AgentRunStatus",
    "AgentToolType",
]
