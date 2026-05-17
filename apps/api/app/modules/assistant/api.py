from __future__ import annotations

import json
from collections.abc import Iterator
from uuid import uuid4

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.assistant.schemas import (
    AssistantChatRequest,
    ChatMessageResponse,
    ChatSessionDetailResponse,
    ChatSessionListResponse,
    ChatSessionResponse,
)
from app.modules.assistant.service import AssistantService
from app.modules.auth.policies import get_current_user, get_current_workspace_id
from app.modules.users.models import User

router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])


def _to_sse(data: dict[str, object] | str) -> str:
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    return f"data: {payload}\n\n"


def _to_ui_message_stream(token_iter: Iterator[str]) -> Iterator[str]:
    """Wrap a token iterator in the Vercel AI SDK UI-message-stream SSE protocol."""
    message_id = f"msg_{uuid4().hex}"
    text_id = f"text_{uuid4().hex}"

    yield _to_sse({"type": "start", "messageId": message_id})
    yield _to_sse({"type": "text-start", "id": text_id})
    for token in token_iter:
        yield _to_sse({"type": "text-delta", "id": text_id, "delta": token})
    yield _to_sse({"type": "text-end", "id": text_id})
    yield _to_sse({"type": "finish"})
    yield _to_sse("[DONE]")


@router.post("/chat")
def chat_with_assistant(
    payload: AssistantChatRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> StreamingResponse:
    service = AssistantService()
    lead = service.resolve_lead(db, workspace_id=workspace_id, lead_public_id=payload.lead_id)
    first_user_text = service._latest_user_message(payload.messages)
    session = service.get_or_create_session(
        db,
        workspace_id=workspace_id,
        session_public_id=payload.session_id,
        lead=lead,
        first_user_message=first_user_text,
    )
    token_stream = service.stream_response(
        db,
        workspace_id=workspace_id,
        messages=payload.messages,
        lead=lead,
        session=session,
    )
    return StreamingResponse(
        _to_ui_message_stream(token_stream),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "x-vercel-ai-ui-message-stream": "v1",
        },
    )


@router.get("/sessions", response_model=ChatSessionListResponse)
def list_sessions(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> ChatSessionListResponse:
    service = AssistantService()
    sessions = service.list_sessions(db, workspace_id=workspace_id)
    return ChatSessionListResponse(
        items=[
            ChatSessionResponse(
                public_id=s.public_id,
                lead_id=None,
                title=s.title,
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
            for s in sessions
        ]
    )


@router.get("/sessions/{session_id}", response_model=ChatSessionDetailResponse)
def get_session(
    session_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> ChatSessionDetailResponse:
    service = AssistantService()
    session = service.get_session_detail(
        db, workspace_id=workspace_id, session_public_id=session_id
    )
    messages = service.session_repository.list_messages(db, session_id=session.id)
    return ChatSessionDetailResponse(
        public_id=session.public_id,
        lead_id=None,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=[
            ChatMessageResponse(
                public_id=m.public_id,
                role=m.role,
                content=m.content,
                created_at=m.created_at,
            )
            for m in messages
        ],
    )


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> None:
    AssistantService().delete_session(
        db, workspace_id=workspace_id, session_public_id=session_id
    )
