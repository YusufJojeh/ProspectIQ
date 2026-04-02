from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.utils.identifiers import new_public_id


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(24), unique=True, default=lambda: new_public_id("pt"))
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    template_text: Mapped[str] = mapped_column(Text())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))


class AIAnalysisSnapshot(Base):
    __tablename__ = "ai_analysis_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(24), unique=True, default=lambda: new_public_id("ais"))
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    prompt_template_id: Mapped[int] = mapped_column(ForeignKey("prompt_templates.id"), index=True)
    ai_provider: Mapped[str] = mapped_column(String(32))
    model_name: Mapped[str] = mapped_column(String(128))
    input_hash: Mapped[str] = mapped_column(String(64), index=True)
    output_json: Mapped[dict] = mapped_column(JSON())
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))

