from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.assistant.models import ChatMessage, ChatSession


class ChatSessionRepository:
    def create_session(
        self,
        db: Session,
        *,
        workspace_id: int,
        lead_id: int | None,
        title: str = "New Chat",
    ) -> ChatSession:
        session = ChatSession(
            workspace_id=workspace_id,
            lead_id=lead_id,
            title=title,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    def get_session_by_public_id(
        self,
        db: Session,
        *,
        workspace_id: int,
        public_id: str,
    ) -> ChatSession | None:
        return db.scalar(
            select(ChatSession).where(
                ChatSession.public_id == public_id,
                ChatSession.workspace_id == workspace_id,
            )
        )

    def list_sessions(
        self,
        db: Session,
        *,
        workspace_id: int,
        limit: int = 50,
    ) -> list[ChatSession]:
        return list(
            db.scalars(
                select(ChatSession)
                .where(ChatSession.workspace_id == workspace_id)
                .order_by(ChatSession.created_at.desc(), ChatSession.id.desc())
                .limit(limit)
            )
        )

    def add_message(
        self,
        db: Session,
        *,
        session_id: int,
        role: str,
        content: str,
    ) -> ChatMessage:
        message = ChatMessage(session_id=session_id, role=role, content=content)
        session = db.get(ChatSession, session_id)
        if session is not None:
            session.updated_at = datetime.now(tz=UTC)
            db.add(session)
        db.add(message)
        db.commit()
        db.refresh(message)
        return message

    def list_messages(
        self,
        db: Session,
        *,
        session_id: int,
    ) -> list[ChatMessage]:
        return list(
            db.scalars(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
            )
        )

    def list_recent_messages(
        self,
        db: Session,
        *,
        session_id: int,
        limit: int,
    ) -> list[ChatMessage]:
        items = list(
            db.scalars(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
                .limit(limit)
            )
        )
        return list(reversed(items))

    def update_session_title(
        self,
        db: Session,
        session: ChatSession,
        title: str,
    ) -> ChatSession:
        session.title = title
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    def delete_session(self, db: Session, session: ChatSession) -> None:
        db.delete(session)
        db.commit()
