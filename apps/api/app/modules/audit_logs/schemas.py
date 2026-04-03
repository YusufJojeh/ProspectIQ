from datetime import datetime

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    public_id: str
    actor_user_public_id: str | None
    event_name: str
    details: str
    created_at: datetime


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
