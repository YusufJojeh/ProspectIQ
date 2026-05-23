from datetime import datetime

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
    session_id: str | None = None
    mode: str = "lead-assistant"


class ChatMessageResponse(BaseModel):
    public_id: str
    role: str
    content: str
    created_at: datetime


class ChatSessionResponse(BaseModel):
    public_id: str
    lead_id: str | None
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    last_message_preview: str | None = None


class ChatSessionDetailResponse(ChatSessionResponse):
    messages: list[ChatMessageResponse]


class ChatSessionListResponse(BaseModel):
    items: list[ChatSessionResponse]


__all__ = [
    "AssistantChatRequest",
    "AssistantMessageInput",
    "AssistantMessagePartInput",
    "ChatMessageResponse",
    "ChatSessionDetailResponse",
    "ChatSessionListResponse",
    "ChatSessionResponse",
]
