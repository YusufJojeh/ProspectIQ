from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints


class OutreachMessageResult(BaseModel):
    subject: str
    message: str


class OutreachDraftResponse(BaseModel):
    public_id: str
    lead_id: str
    ai_analysis_snapshot_public_id: str
    subject: str
    message: str
    generated_subject: str
    generated_message: str
    has_manual_edits: bool
    created_at: datetime
    updated_at: datetime


class LatestOutreachResponse(BaseModel):
    lead_id: str
    message: OutreachDraftResponse | None = None


class OutreachMessageUpdateRequest(BaseModel):
    subject: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8000)]
