from pydantic import BaseModel, Field


class LeadScoreContext(BaseModel):
    total_score: float | None = None
    band: str | None = None
    qualified: bool | None = None
    reasons: list[str] = Field(default_factory=list)
