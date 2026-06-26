from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.campaigns.models import Campaign
from app.modules.crm.models import CrmActivity, CrmDeal, CrmPipeline, CrmStage
from app.modules.leads.models import Lead


class CrmRepository:
    def list_pipelines(self, db: Session, workspace_id: int) -> list[CrmPipeline]:
        return list(
            db.scalars(
                select(CrmPipeline)
                .where(CrmPipeline.workspace_id == workspace_id)
                .order_by(CrmPipeline.is_default.desc(), CrmPipeline.updated_at.desc())
            )
        )

    def get_pipeline(
        self, db: Session, *, workspace_id: int, pipeline_public_id: str
    ) -> CrmPipeline | None:
        return db.scalar(
            select(CrmPipeline).where(
                CrmPipeline.workspace_id == workspace_id,
                CrmPipeline.public_id == pipeline_public_id,
            )
        )

    def get_default_pipeline(self, db: Session, workspace_id: int) -> CrmPipeline | None:
        return db.scalar(
            select(CrmPipeline).where(
                CrmPipeline.workspace_id == workspace_id,
                CrmPipeline.is_default.is_(True),
            )
        )

    def add_pipeline(self, db: Session, pipeline: CrmPipeline) -> CrmPipeline:
        db.add(pipeline)
        db.commit()
        db.refresh(pipeline)
        return pipeline

    def save_pipeline(self, db: Session, pipeline: CrmPipeline) -> CrmPipeline:
        pipeline.updated_at = datetime.now(tz=UTC)
        db.add(pipeline)
        db.commit()
        db.refresh(pipeline)
        return pipeline

    def list_stages(self, db: Session, pipeline_id: int) -> list[CrmStage]:
        return list(
            db.scalars(
                select(CrmStage)
                .where(CrmStage.pipeline_id == pipeline_id)
                .order_by(CrmStage.position.asc(), CrmStage.id.asc())
            )
        )

    def get_stage(
        self, db: Session, *, workspace_id: int, stage_public_id: str
    ) -> CrmStage | None:
        return db.scalar(
            select(CrmStage).where(
                CrmStage.workspace_id == workspace_id,
                CrmStage.public_id == stage_public_id,
            )
        )

    def add_stage(self, db: Session, stage: CrmStage) -> CrmStage:
        db.add(stage)
        db.commit()
        db.refresh(stage)
        return stage

    def save_stage(self, db: Session, stage: CrmStage) -> CrmStage:
        stage.updated_at = datetime.now(tz=UTC)
        db.add(stage)
        db.commit()
        db.refresh(stage)
        return stage

    def list_deals(
        self,
        db: Session,
        *,
        workspace_id: int,
        pipeline_id: int | None = None,
        stage_id: int | None = None,
        lead_id: int | None = None,
        campaign_id: int | None = None,
        status: str | None = None,
    ) -> list[CrmDeal]:
        statement = select(CrmDeal).where(CrmDeal.workspace_id == workspace_id)
        if pipeline_id is not None:
            statement = statement.where(CrmDeal.pipeline_id == pipeline_id)
        if stage_id is not None:
            statement = statement.where(CrmDeal.stage_id == stage_id)
        if lead_id is not None:
            statement = statement.where(CrmDeal.lead_id == lead_id)
        if campaign_id is not None:
            statement = statement.where(CrmDeal.campaign_id == campaign_id)
        if status is not None:
            statement = statement.where(CrmDeal.status == status)
        return list(db.scalars(statement.order_by(CrmDeal.updated_at.desc(), CrmDeal.id.desc())))

    def get_deal(self, db: Session, *, workspace_id: int, deal_public_id: str) -> CrmDeal | None:
        return db.scalar(
            select(CrmDeal).where(
                CrmDeal.workspace_id == workspace_id,
                CrmDeal.public_id == deal_public_id,
            )
        )

    def get_open_deal_for_lead(self, db: Session, *, workspace_id: int, lead_id: int) -> CrmDeal | None:
        return db.scalar(
            select(CrmDeal)
            .where(
                CrmDeal.workspace_id == workspace_id,
                CrmDeal.lead_id == lead_id,
                CrmDeal.status == "open",
            )
            .order_by(CrmDeal.updated_at.desc(), CrmDeal.id.desc())
        )

    def add_deal(self, db: Session, deal: CrmDeal) -> CrmDeal:
        db.add(deal)
        db.commit()
        db.refresh(deal)
        return deal

    def save_deal(self, db: Session, deal: CrmDeal) -> CrmDeal:
        deal.updated_at = datetime.now(tz=UTC)
        db.add(deal)
        db.commit()
        db.refresh(deal)
        return deal

    def list_activities(self, db: Session, deal_id: int) -> list[CrmActivity]:
        return list(
            db.scalars(
                select(CrmActivity)
                .where(CrmActivity.deal_id == deal_id)
                .order_by(CrmActivity.created_at.desc(), CrmActivity.id.desc())
            )
        )

    def get_activity(
        self, db: Session, *, workspace_id: int, activity_public_id: str
    ) -> CrmActivity | None:
        return db.scalar(
            select(CrmActivity).where(
                CrmActivity.workspace_id == workspace_id,
                CrmActivity.public_id == activity_public_id,
            )
        )

    def add_activity(self, db: Session, activity: CrmActivity) -> CrmActivity:
        db.add(activity)
        db.commit()
        db.refresh(activity)
        return activity

    def save_activity(self, db: Session, activity: CrmActivity) -> CrmActivity:
        activity.updated_at = datetime.now(tz=UTC)
        db.add(activity)
        db.commit()
        db.refresh(activity)
        return activity

    def stage_counts(self, db: Session, stage_ids: list[int]) -> dict[int, tuple[int, float]]:
        if not stage_ids:
            return {}
        rows = db.execute(
            select(
                CrmDeal.stage_id,
                func.count(CrmDeal.id),
                func.coalesce(func.sum(CrmDeal.value_amount), 0),
            )
            .where(CrmDeal.stage_id.in_(stage_ids), CrmDeal.status == "open")
            .group_by(CrmDeal.stage_id)
        ).all()
        return {int(stage_id): (int(count), float(total or 0)) for stage_id, count, total in rows}

    def load_response_rows(
        self, db: Session, deal_ids: list[int]
    ) -> dict[int, tuple[CrmPipeline, CrmStage, Lead, Campaign | None]]:
        if not deal_ids:
            return {}
        rows = db.execute(
            select(CrmDeal.id, CrmPipeline, CrmStage, Lead, Campaign)
            .join(CrmPipeline, CrmPipeline.id == CrmDeal.pipeline_id)
            .join(CrmStage, CrmStage.id == CrmDeal.stage_id)
            .join(Lead, Lead.id == CrmDeal.lead_id)
            .outerjoin(Campaign, Campaign.id == CrmDeal.campaign_id)
            .where(CrmDeal.id.in_(deal_ids))
        ).all()
        return {
            int(deal_id): (pipeline, stage, lead, campaign)
            for deal_id, pipeline, stage, lead, campaign in rows
        }
