from pydantic import BaseModel, Field


class AssistantMessagePartInput(BaseModel):
    type: str
    text: str | None = None


class AssistantMessageInput(BaseModel):
    id: str | None = None
    role: str
    parts: list[AssistantMessagePartInput] = Field(default_factory=list)


class AssistantChatRequest(BaseModel):
    messages: list[AssistantMessageInput] = Field(default_factory=list)
    lead_id: str | None = None
    mode: str = "lead-assistant"


__all__ = [
    "AssistantChatRequest",
    "AssistantMessageInput",
    "AssistantMessagePartInput",
]
