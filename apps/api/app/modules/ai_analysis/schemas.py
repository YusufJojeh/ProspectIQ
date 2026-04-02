from pydantic import BaseModel, Field


class LeadAnalysisResult(BaseModel):
    summary: str
    weaknesses: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    recommended_services: list[str] = Field(default_factory=list)
    outreach_subject: str
    outreach_message: str
    confidence: float = Field(ge=0, le=1)

