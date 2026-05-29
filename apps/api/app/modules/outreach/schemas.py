from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints, field_validator

from app.shared.enums.jobs import OutreachTone

_SUPPORTED_LANGUAGES = {"en", "ar"}


class OutreachMessageResult(BaseModel):
    subject: str
    message: str
    tone: OutreachTone


class OutreachGenerateRequest(BaseModel):
    tone: OutreachTone = OutreachTone.CONSULTATIVE
    regenerate: bool = False
    language: str = "en"

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        if v not in _SUPPORTED_LANGUAGES:
            raise ValueError(
                f"language must be one of: {', '.join(sorted(_SUPPORTED_LANGUAGES))}"
            )
        return v


class OutreachDraftResponse(BaseModel):
    public_id: str
    lead_id: str
    ai_analysis_snapshot_public_id: str
    subject: str
    message: str
    tone: OutreachTone
    language: str
    version_number: int
    generated_subject: str
    generated_message: str
    has_manual_edits: bool
    outreach_status: str
    created_at: datetime
    updated_at: datetime


class OutreachSendResponse(BaseModel):
    status: str


class LatestOutreachResponse(BaseModel):
    lead_id: str
    message: OutreachDraftResponse | None = None


class OutreachMessageUpdateRequest(BaseModel):
    subject: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8000)]
