from __future__ import annotations

import json
from collections.abc import Iterable
from uuid import uuid4

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.assistant.schemas import AssistantChatRequest
from app.modules.assistant.service import AssistantService
from app.modules.auth.policies import get_current_user, get_current_workspace_id
from app.modules.users.models import User

router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])


def _to_sse(data: dict[str, object] | str) -> str:
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    return f"data: {payload}\n\n"


def _chunk_text(value: str, size: int = 36) -> Iterable[str]:
    for index in range(0, len(value), size):
        yield value[index : index + size]


def _ui_message_stream(markdown: str) -> Iterable[str]:
    message_id = f"msg_{uuid4().hex}"
    text_id = f"text_{uuid4().hex}"

    yield _to_sse({"type": "start", "messageId": message_id})
    yield _to_sse({"type": "text-start", "id": text_id})
    for chunk in _chunk_text(markdown):
        yield _to_sse({"type": "text-delta", "id": text_id, "delta": chunk})
    yield _to_sse({"type": "text-end", "id": text_id})
    yield _to_sse({"type": "finish"})
    yield _to_sse("[DONE]")


@router.post("/chat")
def chat_with_assistant(
    payload: AssistantChatRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
):
    markdown = AssistantService().generate_response(
        db,
        workspace_id=workspace_id,
        messages=payload.messages,
        lead_public_id=payload.lead_id,
    )
    return StreamingResponse(
        _ui_message_stream(markdown),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "x-vercel-ai-ui-message-stream": "v1",
        },
    )
