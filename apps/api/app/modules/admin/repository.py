from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.ai_analysis.models import PromptTemplate
from app.modules.provider_serpapi.models import ProviderSettings
from app.modules.scoring.models import ScoringConfigVersion


class AdminRepository:
    def get_scoring_version(
        self, db: Session, *, workspace_id: int, public_id: str
    ) -> ScoringConfigVersion | None:
        return db.scalar(
            select(ScoringConfigVersion).where(
                ScoringConfigVersion.workspace_id == workspace_id,
                ScoringConfigVersion.public_id == public_id,
            )
        )

    def get_prompt_template(
        self, db: Session, *, workspace_id: int, public_id: str
    ) -> PromptTemplate | None:
        return db.scalar(
            select(PromptTemplate).where(
                PromptTemplate.workspace_id == workspace_id,
                PromptTemplate.public_id == public_id,
            )
        )

    def get_provider_settings(self, db: Session, *, workspace_id: int) -> ProviderSettings | None:
        return db.scalar(select(ProviderSettings).where(ProviderSettings.workspace_id == workspace_id))

    def ensure_provider_settings(self, db: Session, *, workspace_id: int) -> ProviderSettings:
        settings = self.get_provider_settings(db, workspace_id=workspace_id)
        if settings is None:
            settings = ProviderSettings(workspace_id=workspace_id)
            db.add(settings)
            db.commit()
            db.refresh(settings)
        return settings

    def save_provider_settings(self, db: Session, settings: ProviderSettings) -> None:
        db.add(settings)
        db.commit()
        db.refresh(settings)
