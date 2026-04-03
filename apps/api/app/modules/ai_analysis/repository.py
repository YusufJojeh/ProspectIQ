from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.ai_analysis.models import AIAnalysisSnapshot, PromptTemplate, ServiceRecommendation


class AIAnalysisRepository:
    def get_active_prompt_template(self, db: Session, workspace_id: int) -> PromptTemplate | None:
        statement = (
            select(PromptTemplate)
            .where(
                PromptTemplate.workspace_id == workspace_id,
                PromptTemplate.is_active == True,  # noqa: E712
            )
            .order_by(PromptTemplate.created_at.desc())
            .limit(1)
        )
        return db.scalar(statement)

    def list_prompt_templates(
        self, db: Session, workspace_id: int, *, limit: int = 50
    ) -> list[PromptTemplate]:
        statement = (
            select(PromptTemplate)
            .where(PromptTemplate.workspace_id == workspace_id)
            .order_by(PromptTemplate.created_at.desc(), PromptTemplate.id.desc())
            .limit(limit)
        )
        return list(db.scalars(statement))

    def add_prompt_template(self, db: Session, template: PromptTemplate) -> PromptTemplate:
        db.add(template)
        db.commit()
        db.refresh(template)
        return template

    def activate_prompt_template(
        self, db: Session, *, workspace_id: int, template: PromptTemplate
    ) -> PromptTemplate:
        active_templates = db.scalars(
            select(PromptTemplate).where(PromptTemplate.workspace_id == workspace_id)
        )
        for item in active_templates:
            item.is_active = item.id == template.id
            db.add(item)
        db.commit()
        db.refresh(template)
        return template

    def get_snapshot_by_input_hash(
        self,
        db: Session,
        *,
        lead_id: int,
        prompt_template_id: int,
        input_hash: str,
    ) -> AIAnalysisSnapshot | None:
        statement = (
            select(AIAnalysisSnapshot)
            .where(
                AIAnalysisSnapshot.lead_id == lead_id,
                AIAnalysisSnapshot.prompt_template_id == prompt_template_id,
                AIAnalysisSnapshot.input_hash == input_hash,
            )
            .order_by(AIAnalysisSnapshot.created_at.desc())
            .limit(1)
        )
        return db.scalar(statement)

    def get_latest_snapshot_for_lead(
        self,
        db: Session,
        *,
        lead_id: int,
    ) -> AIAnalysisSnapshot | None:
        statement = (
            select(AIAnalysisSnapshot)
            .where(AIAnalysisSnapshot.lead_id == lead_id)
            .order_by(AIAnalysisSnapshot.created_at.desc(), AIAnalysisSnapshot.id.desc())
            .limit(1)
        )
        return db.scalar(statement)

    def get_snapshot_by_id(self, db: Session, snapshot_id: int) -> AIAnalysisSnapshot | None:
        return db.scalar(select(AIAnalysisSnapshot).where(AIAnalysisSnapshot.id == snapshot_id))

    def add_snapshot(self, db: Session, snapshot: AIAnalysisSnapshot) -> AIAnalysisSnapshot:
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)
        return snapshot

    def add_service_recommendations(
        self,
        db: Session,
        items: list[ServiceRecommendation],
    ) -> list[ServiceRecommendation]:
        if not items:
            return []
        db.add_all(items)
        db.commit()
        for item in items:
            db.refresh(item)
        return items

    def list_service_recommendations(
        self,
        db: Session,
        *,
        snapshot_id: int,
    ) -> list[ServiceRecommendation]:
        statement = (
            select(ServiceRecommendation)
            .where(ServiceRecommendation.ai_analysis_snapshot_id == snapshot_id)
            .order_by(ServiceRecommendation.rank_order.asc(), ServiceRecommendation.id.asc())
        )
        return list(db.scalars(statement))
