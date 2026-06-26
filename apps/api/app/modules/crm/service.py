from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.modules.audit_logs.service import AuditLogService
from app.modules.campaigns.models import Campaign
from app.modules.campaigns.repository import CampaignRepository
from app.modules.crm.models import CrmActivity, CrmDeal, CrmPipeline, CrmStage
from app.modules.crm.repository import CrmRepository
from app.modules.crm.schemas import (
    ActivityCreateRequest,
    ActivityResponse,
    ActivityType,
    ActivityUpdateRequest,
    CampaignCreateDealsResponse,
    DealActionResponse,
    DealCreateRequest,
    DealDetailResponse,
    DealListResponse,
    DealLostRequest,
    DealMoveRequest,
    DealResponse,
    DealStatus,
    DealUpdateRequest,
    PipelineCreateRequest,
    PipelineListResponse,
    PipelineResponse,
    PipelineUpdateRequest,
    StageCreateRequest,
    StageReorderRequest,
    StageResponse,
    StageType,
    StageUpdateRequest,
)
from app.modules.leads.models import Lead
from app.modules.leads.repository import LeadsRepository
from app.modules.leads.service import LeadsService
from app.modules.outreach.repository import OutreachRepository
from app.modules.signals.repository import LeadSignalRepository
from app.modules.users.models import User

DEFAULT_STAGES: tuple[tuple[str, int, str, StageType], ...] = (
    ("New Opportunity", 10, "slate", StageType.OPEN),
    ("Contacted", 20, "blue", StageType.OPEN),
    ("Interested", 40, "cyan", StageType.OPEN),
    ("Proposal / Offer", 60, "amber", StageType.OPEN),
    ("Negotiation", 80, "orange", StageType.OPEN),
    ("Won", 100, "emerald", StageType.WON),
    ("Lost", 0, "rose", StageType.LOST),
)


class CrmService:
    def __init__(self) -> None:
        self.repository = CrmRepository()
        self.leads_repository = LeadsRepository()
        self.leads_service = LeadsService()
        self.outreach_repository = OutreachRepository()
        self.signal_repository = LeadSignalRepository()
        self.campaign_repository = CampaignRepository()
        self.audit_logs = AuditLogService()

    def list_pipelines(
        self, db: Session, *, workspace_id: int, current_user: User
    ) -> PipelineListResponse:
        self.ensure_default_pipeline(db, workspace_id=workspace_id, current_user=current_user)
        pipelines = self.repository.list_pipelines(db, workspace_id)
        return PipelineListResponse(items=[self._to_pipeline_response(db, item) for item in pipelines])

    def create_pipeline(
        self,
        db: Session,
        *,
        workspace_id: int,
        current_user: User,
        payload: PipelineCreateRequest,
    ) -> PipelineResponse:
        pipeline = self.repository.add_pipeline(
            db,
            CrmPipeline(
                workspace_id=workspace_id,
                name=payload.name,
                description=payload.description,
                is_default=False,
                created_by_user_id=current_user.id,
            ),
        )
        self._seed_default_stages(db, workspace_id=workspace_id, pipeline=pipeline)
        self._record(db, workspace_id, "crm.pipeline_created", f"Created pipeline {pipeline.name}.", current_user)
        return self._to_pipeline_response(db, pipeline)

    def get_pipeline(
        self, db: Session, *, workspace_id: int, pipeline_id: str, current_user: User
    ) -> PipelineResponse:
        if pipeline_id == "default":
            pipeline = self.ensure_default_pipeline(
                db, workspace_id=workspace_id, current_user=current_user
            )
        else:
            pipeline = self._get_pipeline_or_raise(
                db, workspace_id=workspace_id, pipeline_id=pipeline_id
            )
        return self._to_pipeline_response(db, pipeline)

    def update_pipeline(
        self,
        db: Session,
        *,
        workspace_id: int,
        pipeline_id: str,
        payload: PipelineUpdateRequest,
        current_user: User,
    ) -> PipelineResponse:
        pipeline = self._get_pipeline_or_raise(
            db, workspace_id=workspace_id, pipeline_id=pipeline_id
        )
        if payload.name is not None:
            pipeline.name = payload.name
        if payload.description is not None:
            pipeline.description = payload.description
        if payload.is_default is not None:
            pipeline.is_default = payload.is_default
        self.repository.save_pipeline(db, pipeline)
        self._record(db, workspace_id, "crm.pipeline_updated", f"Updated pipeline {pipeline.name}.", current_user)
        return self._to_pipeline_response(db, pipeline)

    def create_stage(
        self,
        db: Session,
        *,
        workspace_id: int,
        pipeline_id: str,
        payload: StageCreateRequest,
        current_user: User,
    ) -> PipelineResponse:
        pipeline = self._get_pipeline_or_raise(
            db, workspace_id=workspace_id, pipeline_id=pipeline_id
        )
        position = len(self.repository.list_stages(db, pipeline.id)) + 1
        self.repository.add_stage(
            db,
            CrmStage(
                workspace_id=workspace_id,
                pipeline_id=pipeline.id,
                name=payload.name,
                position=position,
                probability=payload.probability,
                color=payload.color,
                stage_type=payload.stage_type.value,
            ),
        )
        self._record(db, workspace_id, "crm.stage_created", f"Created stage {payload.name}.", current_user)
        return self._to_pipeline_response(db, pipeline)

    def update_stage(
        self,
        db: Session,
        *,
        workspace_id: int,
        pipeline_id: str,
        stage_id: str,
        payload: StageUpdateRequest,
        current_user: User,
    ) -> StageResponse:
        pipeline = self._get_pipeline_or_raise(
            db, workspace_id=workspace_id, pipeline_id=pipeline_id
        )
        stage = self._get_stage_or_raise(db, workspace_id=workspace_id, stage_id=stage_id)
        if stage.pipeline_id != pipeline.id:
            raise NotFoundError("Stage was not found.")
        if payload.name is not None:
            stage.name = payload.name
        if payload.probability is not None:
            stage.probability = payload.probability
        if payload.color is not None:
            stage.color = payload.color
        if payload.stage_type is not None:
            stage.stage_type = payload.stage_type.value
        saved = self.repository.save_stage(db, stage)
        self._record(db, workspace_id, "crm.stage_updated", f"Updated stage {saved.name}.", current_user)
        return self._to_stage_response(db, saved, self.repository.stage_counts(db, [saved.id]))

    def reorder_stages(
        self,
        db: Session,
        *,
        workspace_id: int,
        pipeline_id: str,
        payload: StageReorderRequest,
        current_user: User,
    ) -> PipelineResponse:
        pipeline = self._get_pipeline_or_raise(
            db, workspace_id=workspace_id, pipeline_id=pipeline_id
        )
        stages = {stage.public_id: stage for stage in self.repository.list_stages(db, pipeline.id)}
        if set(stages) != set(payload.stage_ids):
            raise NotFoundError("Stage order does not match this pipeline.")
        for position, public_id in enumerate(payload.stage_ids, start=1):
            stage = stages[public_id]
            stage.position = position
            stage.updated_at = datetime.now(tz=UTC)
            db.add(stage)
        db.commit()
        self._record(db, workspace_id, "crm.stage_reordered", "Reordered CRM stages.", current_user)
        return self._to_pipeline_response(db, pipeline)

    def list_deals(
        self,
        db: Session,
        *,
        workspace_id: int,
        current_user: User,
        pipeline_id: str | None = None,
        stage_id: str | None = None,
        lead_id: str | None = None,
        campaign_id: str | None = None,
        status: DealStatus | None = None,
    ) -> DealListResponse:
        pipeline_db_id = self._optional_pipeline_db_id(
            db, workspace_id=workspace_id, pipeline_id=pipeline_id, current_user=current_user
        )
        stage_db_id = self._optional_stage_db_id(db, workspace_id=workspace_id, stage_id=stage_id)
        lead_db_id = self._optional_lead_db_id(db, workspace_id=workspace_id, lead_id=lead_id)
        campaign_db_id = self._optional_campaign_db_id(
            db, workspace_id=workspace_id, campaign_id=campaign_id
        )
        deals = self.repository.list_deals(
            db,
            workspace_id=workspace_id,
            pipeline_id=pipeline_db_id,
            stage_id=stage_db_id,
            lead_id=lead_db_id,
            campaign_id=campaign_db_id,
            status=status.value if status is not None else None,
        )
        return DealListResponse(items=self._deal_responses(db, workspace_id=workspace_id, deals=deals))

    def create_deal(
        self,
        db: Session,
        *,
        workspace_id: int,
        current_user: User,
        payload: DealCreateRequest,
    ) -> DealResponse:
        lead = self._get_lead_or_raise(db, workspace_id=workspace_id, lead_id=payload.lead_id)
        if not payload.allow_duplicate_open:
            existing = self.repository.get_open_deal_for_lead(
                db, workspace_id=workspace_id, lead_id=lead.id
            )
            if existing is not None:
                raise ConflictError("Lead already has an open deal.")
        pipeline = self._resolve_pipeline_for_deal(
            db, workspace_id=workspace_id, current_user=current_user, pipeline_id=payload.pipeline_id
        )
        stage = self._resolve_stage_for_deal(
            db, workspace_id=workspace_id, pipeline=pipeline, stage_id=payload.stage_id
        )
        campaign = self._resolve_campaign(
            db, workspace_id=workspace_id, campaign_id=payload.campaign_id
        )
        owner = self._resolve_owner(db, workspace_id=workspace_id, owner_public_id=payload.owner_user_id)
        deal = self.repository.add_deal(
            db,
            CrmDeal(
                workspace_id=workspace_id,
                pipeline_id=pipeline.id,
                stage_id=stage.id,
                lead_id=lead.id,
                campaign_id=campaign.id if campaign is not None else None,
                owner_user_id=owner.id if owner is not None else current_user.id,
                title=payload.title or f"{lead.company_name} opportunity",
                value_amount=self._money(payload.value_amount),
                currency=payload.currency.upper(),
                probability=payload.probability if payload.probability is not None else stage.probability,
                expected_close_date=payload.expected_close_date,
                next_follow_up_at=payload.next_follow_up_at,
                created_by_user_id=current_user.id,
            ),
        )
        self._record(db, workspace_id, "crm.deal_created", f"Created deal {deal.public_id}.", current_user)
        return self._deal_responses(db, workspace_id=workspace_id, deals=[deal])[0]

    def get_deal(
        self, db: Session, *, workspace_id: int, deal_id: str
    ) -> DealDetailResponse:
        deal = self._get_deal_or_raise(db, workspace_id=workspace_id, deal_id=deal_id)
        response = self._deal_responses(db, workspace_id=workspace_id, deals=[deal])[0]
        activities = self._activity_responses(db, deal_id=deal.id)
        return DealDetailResponse(**response.model_dump(), activities=activities)

    def update_deal(
        self,
        db: Session,
        *,
        workspace_id: int,
        deal_id: str,
        payload: DealUpdateRequest,
        current_user: User,
    ) -> DealResponse:
        deal = self._get_deal_or_raise(db, workspace_id=workspace_id, deal_id=deal_id)
        if payload.stage_id is not None:
            stage = self._get_stage_or_raise(db, workspace_id=workspace_id, stage_id=payload.stage_id)
            if stage.pipeline_id != deal.pipeline_id:
                raise NotFoundError("Stage was not found.")
            deal.stage_id = stage.id
            deal.probability = stage.probability
        if payload.owner_user_id is not None:
            owner = self._resolve_owner(
                db, workspace_id=workspace_id, owner_public_id=payload.owner_user_id
            )
            deal.owner_user_id = owner.id if owner is not None else None
        if payload.title is not None:
            deal.title = payload.title
        if payload.value_amount is not None:
            deal.value_amount = self._money(payload.value_amount)
        if payload.currency is not None:
            deal.currency = payload.currency.upper()
        if payload.probability is not None:
            deal.probability = payload.probability
        if payload.status is not None:
            deal.status = payload.status.value
        if payload.lost_reason is not None:
            deal.lost_reason = payload.lost_reason
        if payload.expected_close_date is not None:
            deal.expected_close_date = payload.expected_close_date
        if payload.next_follow_up_at is not None:
            deal.next_follow_up_at = payload.next_follow_up_at
        saved = self.repository.save_deal(db, deal)
        self._record(db, workspace_id, "crm.deal_updated", f"Updated deal {saved.public_id}.", current_user)
        return self._deal_responses(db, workspace_id=workspace_id, deals=[saved])[0]

    def archive_deal(
        self, db: Session, *, workspace_id: int, deal_id: str, current_user: User
    ) -> DealActionResponse:
        deal = self._get_deal_or_raise(db, workspace_id=workspace_id, deal_id=deal_id)
        deal.status = DealStatus.ARCHIVED.value
        saved = self.repository.save_deal(db, deal)
        self._record(db, workspace_id, "crm.deal_archived", f"Archived deal {saved.public_id}.", current_user)
        return DealActionResponse(
            status="archived",
            deal=self._deal_responses(db, workspace_id=workspace_id, deals=[saved])[0],
        )

    def move_deal(
        self,
        db: Session,
        *,
        workspace_id: int,
        deal_id: str,
        payload: DealMoveRequest,
        current_user: User,
    ) -> DealResponse:
        deal = self._get_deal_or_raise(db, workspace_id=workspace_id, deal_id=deal_id)
        stage = self._get_stage_or_raise(db, workspace_id=workspace_id, stage_id=payload.stage_id)
        if stage.pipeline_id != deal.pipeline_id:
            raise NotFoundError("Stage was not found.")
        previous_stage_id = deal.stage_id
        deal.stage_id = stage.id
        deal.probability = stage.probability
        deal.status = self._status_for_stage(stage)
        deal.last_activity_at = datetime.now(tz=UTC)
        saved = self.repository.save_deal(db, deal)
        self.create_activity(
            db,
            workspace_id=workspace_id,
            deal_id=saved.public_id,
            payload=ActivityCreateRequest(
                activity_type=ActivityType.STATUS_CHANGE,
                title=f"Moved to {stage.name}",
                metadata={"from_stage_id": previous_stage_id, "to_stage_id": stage.id},
            ),
            current_user=current_user,
        )
        self._record(db, workspace_id, "crm.deal_moved", f"Moved deal {saved.public_id}.", current_user)
        return self._deal_responses(db, workspace_id=workspace_id, deals=[saved])[0]

    def mark_won(
        self, db: Session, *, workspace_id: int, deal_id: str, current_user: User
    ) -> DealResponse:
        return self._mark_terminal(
            db,
            workspace_id=workspace_id,
            deal_id=deal_id,
            status=DealStatus.WON,
            stage_type=StageType.WON,
            lost_reason=None,
            current_user=current_user,
        )

    def mark_lost(
        self,
        db: Session,
        *,
        workspace_id: int,
        deal_id: str,
        payload: DealLostRequest,
        current_user: User,
    ) -> DealResponse:
        return self._mark_terminal(
            db,
            workspace_id=workspace_id,
            deal_id=deal_id,
            status=DealStatus.LOST,
            stage_type=StageType.LOST,
            lost_reason=payload.lost_reason,
            current_user=current_user,
        )

    def create_activity(
        self,
        db: Session,
        *,
        workspace_id: int,
        deal_id: str,
        payload: ActivityCreateRequest,
        current_user: User,
    ) -> ActivityResponse:
        deal = self._get_deal_or_raise(db, workspace_id=workspace_id, deal_id=deal_id)
        activity = self.repository.add_activity(
            db,
            CrmActivity(
                workspace_id=workspace_id,
                deal_id=deal.id,
                activity_type=payload.activity_type.value,
                title=payload.title,
                note=payload.note,
                due_at=payload.due_at,
                actor_user_id=current_user.id,
                metadata_json=payload.metadata,
            ),
        )
        deal.last_activity_at = datetime.now(tz=UTC)
        if payload.activity_type == ActivityType.FOLLOW_UP and payload.due_at is not None:
            deal.next_follow_up_at = payload.due_at
        self.repository.save_deal(db, deal)
        self._record(db, workspace_id, "crm.activity_created", f"Created activity {activity.public_id}.", current_user)
        return self._activity_responses(db, deal_id=deal.id, activities=[activity])[0]

    def update_activity(
        self,
        db: Session,
        *,
        workspace_id: int,
        deal_id: str,
        activity_id: str,
        payload: ActivityUpdateRequest,
        current_user: User,
    ) -> ActivityResponse:
        deal = self._get_deal_or_raise(db, workspace_id=workspace_id, deal_id=deal_id)
        activity = self._get_activity_or_raise(
            db, workspace_id=workspace_id, activity_id=activity_id
        )
        if activity.deal_id != deal.id:
            raise NotFoundError("Activity was not found.")
        if payload.activity_type is not None:
            activity.activity_type = payload.activity_type.value
        if payload.title is not None:
            activity.title = payload.title
        if payload.note is not None:
            activity.note = payload.note
        if payload.due_at is not None:
            activity.due_at = payload.due_at
        if payload.completed_at is not None:
            activity.completed_at = payload.completed_at
        if payload.metadata is not None:
            activity.metadata_json = payload.metadata
        saved = self.repository.save_activity(db, activity)
        deal.last_activity_at = datetime.now(tz=UTC)
        self.repository.save_deal(db, deal)
        self._record(db, workspace_id, "crm.activity_updated", f"Updated activity {saved.public_id}.", current_user)
        return self._activity_responses(db, deal_id=deal.id, activities=[saved])[0]

    def complete_activity(
        self,
        db: Session,
        *,
        workspace_id: int,
        deal_id: str,
        activity_id: str,
        current_user: User,
    ) -> ActivityResponse:
        return self.update_activity(
            db,
            workspace_id=workspace_id,
            deal_id=deal_id,
            activity_id=activity_id,
            payload=ActivityUpdateRequest(completed_at=datetime.now(tz=UTC)),
            current_user=current_user,
        )

    def create_deal_from_lead(
        self,
        db: Session,
        *,
        workspace_id: int,
        lead_id: str,
        current_user: User,
        allow_duplicate_open: bool = False,
    ) -> DealResponse:
        return self.create_deal(
            db,
            workspace_id=workspace_id,
            current_user=current_user,
            payload=DealCreateRequest(
                lead_id=lead_id,
                owner_user_id=current_user.public_id,
                allow_duplicate_open=allow_duplicate_open,
            ),
        )

    def create_deals_from_campaign(
        self,
        db: Session,
        *,
        workspace_id: int,
        campaign_id: str,
        current_user: User,
        allow_duplicate_open: bool = False,
    ) -> CampaignCreateDealsResponse:
        campaign = self._get_campaign_or_raise(
            db, workspace_id=workspace_id, campaign_id=campaign_id
        )
        campaign_leads = self.campaign_repository.list_campaign_leads(db, campaign.id)
        created: list[DealResponse] = []
        skipped: list[str] = []
        for campaign_lead in campaign_leads:
            lead = self.leads_repository.get_by_id_for_workspace(
                db, workspace_id=workspace_id, lead_id=campaign_lead.lead_id
            )
            if lead is None:
                continue
            if (
                not allow_duplicate_open
                and self.repository.get_open_deal_for_lead(
                    db, workspace_id=workspace_id, lead_id=lead.id
                )
                is not None
            ):
                skipped.append(lead.public_id)
                continue
            created.append(
                self.create_deal(
                    db,
                    workspace_id=workspace_id,
                    current_user=current_user,
                    payload=DealCreateRequest(
                        lead_id=lead.public_id,
                        campaign_id=campaign.public_id,
                        owner_user_id=current_user.public_id,
                        allow_duplicate_open=allow_duplicate_open,
                    ),
                )
            )
        return CampaignCreateDealsResponse(
            created_count=len(created),
            skipped_count=len(skipped),
            deals=created,
            skipped_lead_ids=skipped,
        )

    def ensure_default_pipeline(
        self, db: Session, *, workspace_id: int, current_user: User
    ) -> CrmPipeline:
        pipeline = self.repository.get_default_pipeline(db, workspace_id)
        if pipeline is not None:
            if not self.repository.list_stages(db, pipeline.id):
                self._seed_default_stages(db, workspace_id=workspace_id, pipeline=pipeline)
            return pipeline
        pipeline = self.repository.add_pipeline(
            db,
            CrmPipeline(
                workspace_id=workspace_id,
                name="Default Sales Pipeline",
                description="Standard opportunity flow for qualified local-business leads.",
                is_default=True,
                created_by_user_id=current_user.id,
            ),
        )
        self._seed_default_stages(db, workspace_id=workspace_id, pipeline=pipeline)
        return pipeline

    def _mark_terminal(
        self,
        db: Session,
        *,
        workspace_id: int,
        deal_id: str,
        status: DealStatus,
        stage_type: StageType,
        lost_reason: str | None,
        current_user: User,
    ) -> DealResponse:
        deal = self._get_deal_or_raise(db, workspace_id=workspace_id, deal_id=deal_id)
        stage = self._terminal_stage(db, deal.pipeline_id, stage_type)
        deal.stage_id = stage.id
        deal.probability = stage.probability
        deal.status = status.value
        deal.lost_reason = lost_reason
        deal.last_activity_at = datetime.now(tz=UTC)
        saved = self.repository.save_deal(db, deal)
        self.create_activity(
            db,
            workspace_id=workspace_id,
            deal_id=saved.public_id,
            payload=ActivityCreateRequest(
                activity_type=ActivityType.STATUS_CHANGE,
                title=f"Marked {status.value}",
                metadata={"status": status.value},
            ),
            current_user=current_user,
        )
        self._record(db, workspace_id, f"crm.deal_{status.value}", f"Marked deal {saved.public_id} {status.value}.", current_user)
        return self._deal_responses(db, workspace_id=workspace_id, deals=[saved])[0]

    def _deal_responses(
        self, db: Session, *, workspace_id: int, deals: list[CrmDeal]
    ) -> list[DealResponse]:
        if not deals:
            return []
        rows = self.repository.load_response_rows(db, [deal.id for deal in deals])
        lead_ids = [rows[deal.id][2].id for deal in deals if deal.id in rows]
        latest_scores = self.leads_repository.get_latest_scores(db, lead_ids)
        assignees = self.leads_repository.get_assignee_public_ids(
            db, [rows[deal.id][2] for deal in deals if deal.id in rows]
        )
        outreach_statuses = self.outreach_repository.get_latest_outreach_statuses(db, lead_ids)
        signal_summaries = self.signal_repository.summaries_for_leads(
            db, workspace_id=workspace_id, lead_ids=lead_ids
        )
        owners = self._users_by_ids(db, [deal.owner_user_id for deal in deals if deal.owner_user_id])
        next_activity_by_deal = self._next_activities(db, [deal.id for deal in deals])
        overdue_counts = self._overdue_counts(db, [deal.id for deal in deals])

        responses: list[DealResponse] = []
        for deal in deals:
            row = rows.get(deal.id)
            if row is None:
                continue
            pipeline, stage, lead, campaign = row
            owner = owners.get(deal.owner_user_id or 0)
            lead_response = self.leads_service._to_response(  # noqa: SLF001
                lead,
                latest_scores.get(lead.id),
                assignees.get(lead.assigned_to_user_id or 0),
                outreach_statuses.get(lead.id),
                signal_summaries.get(lead.id),
            )
            next_activity = next_activity_by_deal.get(deal.id)
            responses.append(
                DealResponse(
                    public_id=deal.public_id,
                    title=deal.title,
                    pipeline_id=pipeline.public_id,
                    pipeline_name=pipeline.name,
                    stage_id=stage.public_id,
                    stage_name=stage.name,
                    stage_probability=stage.probability,
                    lead=lead_response,
                    campaign_id=campaign.public_id if campaign is not None else None,
                    campaign_name=campaign.name if campaign is not None else None,
                    owner_user_id=owner.public_id if owner is not None else None,
                    owner_full_name=owner.full_name if owner is not None else None,
                    value_amount=float(deal.value_amount) if deal.value_amount is not None else None,
                    currency=deal.currency,
                    probability=deal.probability,
                    status=DealStatus(deal.status),
                    lost_reason=deal.lost_reason,
                    expected_close_date=deal.expected_close_date,
                    next_follow_up_at=deal.next_follow_up_at,
                    last_activity_at=deal.last_activity_at,
                    next_activity=(
                        self._activity_responses(db, deal_id=deal.id, activities=[next_activity])[0]
                        if next_activity is not None
                        else None
                    ),
                    overdue_activity_count=overdue_counts.get(deal.id, 0),
                    created_at=deal.created_at,
                    updated_at=deal.updated_at,
                )
            )
        return responses

    def _activity_responses(
        self,
        db: Session,
        *,
        deal_id: int,
        activities: list[CrmActivity] | None = None,
    ) -> list[ActivityResponse]:
        items = activities if activities is not None else self.repository.list_activities(db, deal_id)
        actors = self._users_by_ids(db, [item.actor_user_id for item in items if item.actor_user_id])
        deal_public_id = db.scalar(select(CrmDeal.public_id).where(CrmDeal.id == deal_id)) or ""
        responses: list[ActivityResponse] = []
        for item in items:
            actor = actors.get(item.actor_user_id or 0)
            responses.append(
                ActivityResponse(
                    public_id=item.public_id,
                    deal_id=deal_public_id,
                    activity_type=ActivityType(item.activity_type),
                    title=item.title,
                    note=item.note,
                    due_at=item.due_at,
                    completed_at=item.completed_at,
                    actor_user_id=actor.public_id if actor is not None else None,
                    actor_full_name=actor.full_name if actor is not None else None,
                    metadata=item.metadata_json,
                    created_at=item.created_at,
                    updated_at=item.updated_at,
                )
            )
        return responses

    def _to_pipeline_response(self, db: Session, pipeline: CrmPipeline) -> PipelineResponse:
        stages = self.repository.list_stages(db, pipeline.id)
        counts = self.repository.stage_counts(db, [stage.id for stage in stages])
        return PipelineResponse(
            public_id=pipeline.public_id,
            name=pipeline.name,
            description=pipeline.description,
            is_default=pipeline.is_default,
            stages=[self._to_stage_response(db, stage, counts) for stage in stages],
            created_at=pipeline.created_at,
            updated_at=pipeline.updated_at,
        )

    def _to_stage_response(
        self, _: Session, stage: CrmStage, counts: dict[int, tuple[int, float]]
    ) -> StageResponse:
        deal_count, total_value = counts.get(stage.id, (0, 0.0))
        return StageResponse(
            public_id=stage.public_id,
            name=stage.name,
            position=stage.position,
            probability=stage.probability,
            color=stage.color,
            stage_type=StageType(stage.stage_type),
            deal_count=deal_count,
            total_value=total_value,
            created_at=stage.created_at,
            updated_at=stage.updated_at,
        )

    def _seed_default_stages(
        self, db: Session, *, workspace_id: int, pipeline: CrmPipeline
    ) -> None:
        for position, (name, probability, color, stage_type) in enumerate(DEFAULT_STAGES, start=1):
            db.add(
                CrmStage(
                    workspace_id=workspace_id,
                    pipeline_id=pipeline.id,
                    name=name,
                    position=position,
                    probability=probability,
                    color=color,
                    stage_type=stage_type.value,
                )
            )
        db.commit()

    def _get_pipeline_or_raise(
        self, db: Session, *, workspace_id: int, pipeline_id: str
    ) -> CrmPipeline:
        pipeline = self.repository.get_pipeline(
            db, workspace_id=workspace_id, pipeline_public_id=pipeline_id
        )
        if pipeline is None:
            raise NotFoundError("Pipeline was not found.")
        return pipeline

    def _get_stage_or_raise(self, db: Session, *, workspace_id: int, stage_id: str) -> CrmStage:
        stage = self.repository.get_stage(db, workspace_id=workspace_id, stage_public_id=stage_id)
        if stage is None:
            raise NotFoundError("Stage was not found.")
        return stage

    def _get_deal_or_raise(self, db: Session, *, workspace_id: int, deal_id: str) -> CrmDeal:
        deal = self.repository.get_deal(db, workspace_id=workspace_id, deal_public_id=deal_id)
        if deal is None:
            raise NotFoundError("Deal was not found.")
        return deal

    def _get_activity_or_raise(
        self, db: Session, *, workspace_id: int, activity_id: str
    ) -> CrmActivity:
        activity = self.repository.get_activity(
            db, workspace_id=workspace_id, activity_public_id=activity_id
        )
        if activity is None:
            raise NotFoundError("Activity was not found.")
        return activity

    def _get_lead_or_raise(self, db: Session, *, workspace_id: int, lead_id: str) -> Lead:
        lead = self.leads_repository.get_by_public_id_for_workspace(
            db, workspace_id=workspace_id, public_id=lead_id
        )
        if lead is None:
            raise NotFoundError("Lead was not found.")
        return lead

    def _get_campaign_or_raise(self, db: Session, *, workspace_id: int, campaign_id: str) -> Campaign:
        campaign = self.campaign_repository.get_by_public_id(
            db, workspace_id=workspace_id, campaign_public_id=campaign_id
        )
        if campaign is None:
            raise NotFoundError("Campaign was not found.")
        return campaign

    def _resolve_campaign(
        self, db: Session, *, workspace_id: int, campaign_id: str | None
    ) -> Campaign | None:
        if campaign_id is None:
            return None
        return self._get_campaign_or_raise(db, workspace_id=workspace_id, campaign_id=campaign_id)

    def _resolve_owner(
        self, db: Session, *, workspace_id: int, owner_public_id: str | None
    ) -> User | None:
        if owner_public_id is None:
            return None
        owner = db.scalar(
            select(User).where(User.workspace_id == workspace_id, User.public_id == owner_public_id)
        )
        if owner is None:
            raise NotFoundError("Owner was not found.")
        return owner

    def _resolve_pipeline_for_deal(
        self, db: Session, *, workspace_id: int, current_user: User, pipeline_id: str | None
    ) -> CrmPipeline:
        if pipeline_id is None:
            return self.ensure_default_pipeline(
                db, workspace_id=workspace_id, current_user=current_user
            )
        return self._get_pipeline_or_raise(db, workspace_id=workspace_id, pipeline_id=pipeline_id)

    def _resolve_stage_for_deal(
        self, db: Session, *, workspace_id: int, pipeline: CrmPipeline, stage_id: str | None
    ) -> CrmStage:
        if stage_id is not None:
            stage = self._get_stage_or_raise(db, workspace_id=workspace_id, stage_id=stage_id)
            if stage.pipeline_id != pipeline.id:
                raise NotFoundError("Stage was not found.")
            return stage
        stages = [
            stage
            for stage in self.repository.list_stages(db, pipeline.id)
            if stage.stage_type == StageType.OPEN.value
        ]
        if not stages:
            raise NotFoundError("Pipeline has no open stages.")
        return stages[0]

    def _terminal_stage(self, db: Session, pipeline_id: int, stage_type: StageType) -> CrmStage:
        stage = next(
            (
                item
                for item in self.repository.list_stages(db, pipeline_id)
                if item.stage_type == stage_type.value
            ),
            None,
        )
        if stage is None:
            raise NotFoundError(f"Pipeline has no {stage_type.value} stage.")
        return stage

    def _optional_pipeline_db_id(
        self,
        db: Session,
        *,
        workspace_id: int,
        pipeline_id: str | None,
        current_user: User,
    ) -> int | None:
        if pipeline_id is None:
            return None
        if pipeline_id == "default":
            return self.ensure_default_pipeline(db, workspace_id=workspace_id, current_user=current_user).id
        return self._get_pipeline_or_raise(db, workspace_id=workspace_id, pipeline_id=pipeline_id).id

    def _optional_stage_db_id(
        self, db: Session, *, workspace_id: int, stage_id: str | None
    ) -> int | None:
        return None if stage_id is None else self._get_stage_or_raise(db, workspace_id=workspace_id, stage_id=stage_id).id

    def _optional_lead_db_id(
        self, db: Session, *, workspace_id: int, lead_id: str | None
    ) -> int | None:
        return None if lead_id is None else self._get_lead_or_raise(db, workspace_id=workspace_id, lead_id=lead_id).id

    def _optional_campaign_db_id(
        self, db: Session, *, workspace_id: int, campaign_id: str | None
    ) -> int | None:
        return None if campaign_id is None else self._get_campaign_or_raise(db, workspace_id=workspace_id, campaign_id=campaign_id).id

    def _users_by_ids(self, db: Session, ids: list[int | None]) -> dict[int, User]:
        clean_ids = [item for item in ids if item is not None]
        if not clean_ids:
            return {}
        return {user.id: user for user in db.scalars(select(User).where(User.id.in_(clean_ids)))}

    def _next_activities(self, db: Session, deal_ids: list[int]) -> dict[int, CrmActivity]:
        if not deal_ids:
            return {}
        rows = db.scalars(
            select(CrmActivity)
            .where(CrmActivity.deal_id.in_(deal_ids), CrmActivity.completed_at.is_(None))
            .order_by(CrmActivity.deal_id.asc(), CrmActivity.due_at.asc(), CrmActivity.id.asc())
        )
        by_deal: dict[int, CrmActivity] = {}
        for activity in rows:
            if activity.deal_id not in by_deal:
                by_deal[activity.deal_id] = activity
        return by_deal

    def _overdue_counts(self, db: Session, deal_ids: list[int]) -> dict[int, int]:
        if not deal_ids:
            return {}
        now = datetime.now(tz=UTC)
        rows = db.execute(
            select(CrmActivity.deal_id, func.count(CrmActivity.id))
            .where(
                CrmActivity.deal_id.in_(deal_ids),
                CrmActivity.completed_at.is_(None),
                CrmActivity.due_at.is_not(None),
                CrmActivity.due_at < now,
            )
            .group_by(CrmActivity.deal_id)
        ).all()
        return {int(deal_id): int(count) for deal_id, count in rows}

    def _status_for_stage(self, stage: CrmStage) -> str:
        if stage.stage_type == StageType.WON.value:
            return DealStatus.WON.value
        if stage.stage_type == StageType.LOST.value:
            return DealStatus.LOST.value
        return DealStatus.OPEN.value

    def _money(self, value: float | None) -> Decimal | None:
        return None if value is None else Decimal(str(value))

    def _record(
        self, db: Session, workspace_id: int, event_name: str, details: str, current_user: User
    ) -> None:
        self.audit_logs.record(
            db,
            workspace_id=workspace_id,
            event_name=event_name,
            details=details,
            actor_user_id=current_user.id,
        )
