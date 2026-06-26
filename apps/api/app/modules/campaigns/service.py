from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.modules.ai_analysis.models import AIAnalysisSnapshot
from app.modules.ai_analysis.schemas import LeadAnalysisResult
from app.modules.ai_analysis.service import AIAnalysisService
from app.modules.campaigns.models import Campaign, CampaignLead, OutreachEvent, SequenceStep
from app.modules.campaigns.repository import CampaignRepository
from app.modules.campaigns.schemas import (
    CampaignActionResponse,
    CampaignCreateRequest,
    CampaignDetailResponse,
    CampaignGenerateDraftsResponse,
    CampaignLeadAddRequest,
    CampaignLeadResponse,
    CampaignLeadStatus,
    CampaignListResponse,
    CampaignResponse,
    CampaignStatus,
    CampaignUpdateRequest,
    OutreachEventResponse,
    SequenceChannel,
    SequenceStepResponse,
    SequenceStepUpdateRequest,
)
from app.modules.leads.models import Lead
from app.modules.leads.repository import LeadsRepository
from app.modules.leads.schemas import LeadResponse
from app.modules.leads.service import LeadsService
from app.modules.outreach.models import OutreachMessage
from app.modules.outreach.repository import OutreachRepository
from app.modules.outreach.schemas import OutreachDraftResponse
from app.modules.outreach.service import OutreachGenerationService
from app.modules.signals.repository import LeadSignalRepository
from app.modules.users.models import User
from app.shared.enums.jobs import OutreachTone


class CampaignService:
    def __init__(self) -> None:
        self.repository = CampaignRepository()
        self.leads_repository = LeadsRepository()
        self.leads_service = LeadsService()
        self.outreach_repository = OutreachRepository()
        self.outreach_service = OutreachGenerationService()
        self.analysis_service = AIAnalysisService()
        self.signal_repository = LeadSignalRepository()

    def list_campaigns(self, db: Session, *, workspace_id: int) -> CampaignListResponse:
        campaigns = self.repository.list_for_workspace(db, workspace_id)
        counts = self.repository.counts_for_campaigns(db, [item.id for item in campaigns])
        icp_public_ids = self._icp_public_ids(db, [item.icp_profile_id for item in campaigns])
        return CampaignListResponse(
            items=[
                self._to_campaign_response(item, counts.get(item.id, (0, 0)), icp_public_ids)
                for item in campaigns
            ]
        )

    def create_campaign(
        self,
        db: Session,
        *,
        workspace_id: int,
        payload: CampaignCreateRequest,
        current_user: User,
    ) -> CampaignDetailResponse:
        icp_profile_id = self._resolve_icp_profile_id(
            db, workspace_id=workspace_id, icp_public_id=payload.icp_profile_id
        )
        campaign = self.repository.add_campaign(
            db,
            Campaign(
                workspace_id=workspace_id,
                name=payload.name,
                description=payload.description,
                icp_profile_id=icp_profile_id,
                created_by_user_id=current_user.id,
            ),
        )
        self._record_event(
            db,
            workspace_id=workspace_id,
            campaign=campaign,
            event_type="campaign.created",
            metadata={"name": campaign.name},
        )
        return self.get_campaign(db, workspace_id=workspace_id, campaign_id=campaign.public_id)

    def get_campaign(
        self, db: Session, *, workspace_id: int, campaign_id: str
    ) -> CampaignDetailResponse:
        campaign = self._get_campaign_or_raise(db, workspace_id=workspace_id, campaign_id=campaign_id)
        counts = self.repository.counts_for_campaigns(db, [campaign.id])
        icp_public_ids = self._icp_public_ids(db, [campaign.icp_profile_id])
        base = self._to_campaign_response(campaign, counts.get(campaign.id, (0, 0)), icp_public_ids)
        campaign_leads = self.repository.list_campaign_leads(db, campaign.id)
        lead_responses = self._lead_responses(db, workspace_id=workspace_id, campaign_leads=campaign_leads)
        lead_response_by_id = {lead_id: response for lead_id, response in lead_responses}
        leads = [
            CampaignLeadResponse(
                lead=lead_response_by_id[item.lead_id],
                status=CampaignLeadStatus(item.status),
                added_at=item.added_at,
            )
            for item in campaign_leads
            if item.lead_id in lead_response_by_id
        ]
        lead_ids = [item.lead_id for item in campaign_leads]
        latest_messages = self.outreach_repository.get_latest_messages_for_leads(db, lead_ids)
        public_id_by_lead_id = {
            lead_id: response.public_id for lead_id, response in lead_responses
        }
        drafts = [
            self.outreach_service._to_response(  # noqa: SLF001
                db,
                lead_public_id=public_id_by_lead_id[message.lead_id],
                message=message,
            )
            for message in latest_messages.values()
            if message.lead_id in public_id_by_lead_id
        ]
        return CampaignDetailResponse(
            **base.model_dump(),
            leads=leads,
            sequence_steps=[
                self._to_sequence_response(step)
                for step in self.repository.list_sequence_steps(db, campaign.id)
            ],
            drafts=drafts,
            events=self._event_responses(db, campaign.id),
        )

    def update_campaign(
        self,
        db: Session,
        *,
        workspace_id: int,
        campaign_id: str,
        payload: CampaignUpdateRequest,
    ) -> CampaignDetailResponse:
        campaign = self._get_campaign_or_raise(db, workspace_id=workspace_id, campaign_id=campaign_id)
        if payload.name is not None:
            campaign.name = payload.name
        if payload.description is not None:
            campaign.description = payload.description
        if payload.status is not None:
            campaign.status = payload.status.value
        self.repository.save_campaign(db, campaign)
        self._record_event(
            db,
            workspace_id=workspace_id,
            campaign=campaign,
            event_type="campaign.updated",
            metadata={"status": campaign.status},
        )
        return self.get_campaign(db, workspace_id=workspace_id, campaign_id=campaign.public_id)

    def archive_campaign(
        self, db: Session, *, workspace_id: int, campaign_id: str
    ) -> CampaignActionResponse:
        campaign = self._get_campaign_or_raise(db, workspace_id=workspace_id, campaign_id=campaign_id)
        campaign.status = CampaignStatus.ARCHIVED.value
        self.repository.save_campaign(db, campaign)
        self._record_event(
            db,
            workspace_id=workspace_id,
            campaign=campaign,
            event_type="campaign.archived",
            metadata=None,
        )
        return CampaignActionResponse(status="archived")

    def add_leads(
        self,
        db: Session,
        *,
        workspace_id: int,
        campaign_id: str,
        payload: CampaignLeadAddRequest,
    ) -> CampaignDetailResponse:
        campaign = self._get_campaign_or_raise(db, workspace_id=workspace_id, campaign_id=campaign_id)
        for lead_public_id in payload.lead_ids:
            lead = self._get_lead_or_raise(db, workspace_id=workspace_id, lead_public_id=lead_public_id)
            existing = self.repository.get_campaign_lead(db, campaign_id=campaign.id, lead_id=lead.id)
            if existing is None:
                self.repository.add_campaign_lead(
                    db,
                    CampaignLead(
                        campaign_id=campaign.id,
                        lead_id=lead.id,
                        status=CampaignLeadStatus.ADDED.value,
                    ),
                )
            elif existing.status == CampaignLeadStatus.REMOVED.value:
                existing.status = CampaignLeadStatus.ADDED.value
                self.repository.save_campaign_lead(db, existing)
            self._record_event(
                db,
                workspace_id=workspace_id,
                campaign=campaign,
                lead=lead,
                event_type="campaign.lead_added",
                metadata={"lead_id": lead.public_id},
            )
        self.repository.save_campaign(db, campaign)
        return self.get_campaign(db, workspace_id=workspace_id, campaign_id=campaign.public_id)

    def remove_lead(
        self,
        db: Session,
        *,
        workspace_id: int,
        campaign_id: str,
        lead_id: str,
    ) -> CampaignActionResponse:
        campaign = self._get_campaign_or_raise(db, workspace_id=workspace_id, campaign_id=campaign_id)
        lead = self._get_lead_or_raise(db, workspace_id=workspace_id, lead_public_id=lead_id)
        campaign_lead = self.repository.get_campaign_lead(db, campaign_id=campaign.id, lead_id=lead.id)
        if campaign_lead is None:
            raise NotFoundError("Campaign lead was not found.")
        self.repository.remove_campaign_lead(db, campaign_lead)
        self._record_event(
            db,
            workspace_id=workspace_id,
            campaign=campaign,
            lead=lead,
            event_type="campaign.lead_removed",
            metadata={"lead_id": lead.public_id},
        )
        self.repository.save_campaign(db, campaign)
        return CampaignActionResponse(status="removed")

    def generate_sequence(
        self, db: Session, *, workspace_id: int, campaign_id: str
    ) -> list[SequenceStepResponse]:
        campaign = self._get_campaign_or_raise(db, workspace_id=workspace_id, campaign_id=campaign_id)
        steps = [
            SequenceStep(
                campaign_id=campaign.id,
                step_order=1,
                channel=SequenceChannel.EMAIL.value,
                delay_days=0,
                tone=OutreachTone.CONSULTATIVE.value,
                language="en",
                template_text=(
                    "Initial outreach: reference the strongest stored evidence, explain one clear "
                    "opportunity, and ask permission to share a concise audit."
                ),
            ),
            SequenceStep(
                campaign_id=campaign.id,
                step_order=2,
                channel=SequenceChannel.EMAIL.value,
                delay_days=3,
                tone=OutreachTone.FRIENDLY.value,
                language="en",
                template_text=(
                    "Polite follow-up: keep it short, restate the evidence-backed opportunity, "
                    "and offer a low-friction next step."
                ),
            ),
            SequenceStep(
                campaign_id=campaign.id,
                step_order=3,
                channel=SequenceChannel.EMAIL.value,
                delay_days=7,
                tone=OutreachTone.SHORT_PITCH.value,
                language="en",
                template_text=(
                    "Final value reminder: avoid pressure, summarize the value hypothesis, "
                    "and close the loop unless they want the audit."
                ),
            ),
        ]
        self.repository.replace_sequence_steps(db, campaign.id, steps)
        self._record_event(
            db,
            workspace_id=workspace_id,
            campaign=campaign,
            event_type="campaign.sequence_generated",
            metadata={"steps": 3},
        )
        self.repository.save_campaign(db, campaign)
        return [self._to_sequence_response(step) for step in self.repository.list_sequence_steps(db, campaign.id)]

    def list_sequence_steps(
        self, db: Session, *, workspace_id: int, campaign_id: str
    ) -> list[SequenceStepResponse]:
        campaign = self._get_campaign_or_raise(db, workspace_id=workspace_id, campaign_id=campaign_id)
        return [self._to_sequence_response(step) for step in self.repository.list_sequence_steps(db, campaign.id)]

    def update_sequence_step(
        self,
        db: Session,
        *,
        workspace_id: int,
        campaign_id: str,
        step_id: str,
        payload: SequenceStepUpdateRequest,
    ) -> SequenceStepResponse:
        campaign = self._get_campaign_or_raise(db, workspace_id=workspace_id, campaign_id=campaign_id)
        step = self.repository.get_sequence_step(db, campaign_id=campaign.id, step_public_id=step_id)
        if step is None:
            raise NotFoundError("Sequence step was not found.")
        if payload.channel is not None:
            step.channel = payload.channel.value
        if payload.delay_days is not None:
            step.delay_days = payload.delay_days
        if payload.tone is not None:
            step.tone = payload.tone
        if payload.language is not None:
            step.language = payload.language
        if payload.template_text is not None:
            step.template_text = payload.template_text
        saved = self.repository.save_sequence_step(db, step)
        self._record_event(
            db,
            workspace_id=workspace_id,
            campaign=campaign,
            event_type="campaign.sequence_step_updated",
            metadata={"step_order": saved.step_order},
        )
        return self._to_sequence_response(saved)

    def generate_drafts(
        self,
        db: Session,
        *,
        workspace_id: int,
        campaign_id: str,
        current_user: User,
    ) -> CampaignGenerateDraftsResponse:
        campaign = self._get_campaign_or_raise(db, workspace_id=workspace_id, campaign_id=campaign_id)
        steps = self.repository.list_sequence_steps(db, campaign.id)
        if not steps:
            self.generate_sequence(db, workspace_id=workspace_id, campaign_id=campaign.public_id)
            steps = self.repository.list_sequence_steps(db, campaign.id)
        campaign_leads = self.repository.list_campaign_leads(db, campaign.id)
        drafts: list[OutreachDraftResponse] = []
        for campaign_lead in campaign_leads:
            lead = self.leads_repository.get_by_id_for_workspace(
                db, workspace_id=workspace_id, lead_id=campaign_lead.lead_id
            )
            if lead is None:
                continue
            snapshot, analysis = self._analysis_for_lead(
                db,
                workspace_id=workspace_id,
                lead=lead,
                created_by_user_id=current_user.id,
            )
            for step in steps:
                self.outreach_service.generate(
                    db,
                    lead=lead,
                    snapshot=snapshot,
                    analysis=analysis,
                    created_by_user_id=current_user.id,
                    tone=self._outreach_tone(step.tone),
                    regenerate=True,
                    language=step.language,
                )
                message = self.outreach_repository.get_latest_by_lead(db, lead.id)
                if message is None:
                    continue
                self._record_event(
                    db,
                    workspace_id=workspace_id,
                    campaign=campaign,
                    lead=lead,
                    message=message,
                    event_type="campaign.draft_generated",
                    metadata={
                        "step_order": step.step_order,
                        "channel": step.channel,
                        "tone": step.tone,
                    },
                )
                drafts.append(
                    self.outreach_service._to_response(  # noqa: SLF001
                        db,
                        lead_public_id=lead.public_id,
                        message=message,
                    )
                )
            campaign_lead.status = CampaignLeadStatus.DRAFTED.value
            self.repository.save_campaign_lead(db, campaign_lead)
        self.repository.save_campaign(db, campaign)
        return CampaignGenerateDraftsResponse(created_count=len(drafts), drafts=drafts)

    def list_events(
        self, db: Session, *, workspace_id: int, campaign_id: str
    ) -> list[OutreachEventResponse]:
        campaign = self._get_campaign_or_raise(db, workspace_id=workspace_id, campaign_id=campaign_id)
        return self._event_responses(db, campaign.id)

    def _analysis_for_lead(
        self,
        db: Session,
        *,
        workspace_id: int,
        lead: Lead,
        created_by_user_id: int,
    ) -> tuple[AIAnalysisSnapshot, LeadAnalysisResult]:
        context = self.analysis_service.lead_intelligence.build(db, lead=lead)
        return self.analysis_service.analyze(
            db,
            workspace_id=workspace_id,
            lead=lead,
            facts=context.facts,
            created_by_user_id=created_by_user_id,
            score_context=context.score_context,
        )

    def _lead_responses(
        self,
        db: Session,
        *,
        workspace_id: int,
        campaign_leads: list[CampaignLead],
    ) -> list[tuple[int, LeadResponse]]:
        lead_ids = [item.lead_id for item in campaign_leads]
        if not lead_ids:
            return []
        leads = list(
            db.scalars(
                select(Lead)
                .where(Lead.workspace_id == workspace_id, Lead.id.in_(lead_ids))
                .order_by(Lead.company_name.asc())
            )
        )
        latest_scores = self.leads_repository.get_latest_scores(db, [lead.id for lead in leads])
        assignees = self.leads_repository.get_assignee_public_ids(db, leads)
        outreach_statuses = self.outreach_repository.get_latest_outreach_statuses(
            db, [lead.id for lead in leads]
        )
        signal_summaries = self.signal_repository.summaries_for_leads(
            db, workspace_id=workspace_id, lead_ids=[lead.id for lead in leads]
        )
        return [
            (
                lead.id,
                self.leads_service._to_response(  # noqa: SLF001
                    lead,
                    latest_scores.get(lead.id),
                    assignees.get(lead.assigned_to_user_id or 0),
                    outreach_statuses.get(lead.id),
                    signal_summaries.get(lead.id),
                ),
            )
            for lead in leads
        ]

    def _get_campaign_or_raise(
        self, db: Session, *, workspace_id: int, campaign_id: str
    ) -> Campaign:
        campaign = self.repository.get_by_public_id(
            db, workspace_id=workspace_id, campaign_public_id=campaign_id
        )
        if campaign is None:
            raise NotFoundError("Campaign was not found.")
        return campaign

    def _get_lead_or_raise(self, db: Session, *, workspace_id: int, lead_public_id: str) -> Lead:
        lead = self.leads_repository.get_by_public_id_for_workspace(
            db, workspace_id=workspace_id, public_id=lead_public_id
        )
        if lead is None:
            raise NotFoundError("Lead was not found.")
        return lead

    def _resolve_icp_profile_id(
        self, db: Session, *, workspace_id: int, icp_public_id: str | None
    ) -> int | None:
        if icp_public_id is None:
            return None
        profile = self.repository.get_icp_by_public_id(
            db, workspace_id=workspace_id, icp_public_id=icp_public_id
        )
        if profile is None:
            raise NotFoundError("ICP profile was not found.")
        return profile.id

    def _icp_public_ids(self, db: Session, ids: list[int | None]) -> dict[int, str]:
        clean_ids = [item for item in ids if item is not None]
        if not clean_ids:
            return {}
        from app.modules.icp.models import IcpProfile

        rows = db.execute(
            select(IcpProfile.id, IcpProfile.public_id).where(IcpProfile.id.in_(clean_ids))
        ).all()
        return {int(row[0]): str(row[1]) for row in rows}

    def _to_campaign_response(
        self,
        campaign: Campaign,
        counts: tuple[int, int],
        icp_public_ids: dict[int, str],
    ) -> CampaignResponse:
        lead_count, sequence_steps_count = counts
        return CampaignResponse(
            public_id=campaign.public_id,
            name=campaign.name,
            description=campaign.description,
            icp_profile_id=(
                icp_public_ids.get(campaign.icp_profile_id)
                if campaign.icp_profile_id is not None
                else None
            ),
            status=CampaignStatus(campaign.status),
            lead_count=lead_count,
            sequence_steps_count=sequence_steps_count,
            created_at=campaign.created_at,
            updated_at=campaign.updated_at,
        )

    def _to_sequence_response(self, step: SequenceStep) -> SequenceStepResponse:
        return SequenceStepResponse(
            public_id=step.public_id,
            step_order=step.step_order,
            channel=SequenceChannel(step.channel),
            delay_days=step.delay_days,
            tone=step.tone,
            language=step.language,
            template_text=step.template_text,
            created_at=step.created_at,
            updated_at=step.updated_at,
        )

    def _event_responses(self, db: Session, campaign_id: int) -> list[OutreachEventResponse]:
        return [
            OutreachEventResponse(
                public_id=event.public_id,
                event_type=event.event_type,
                occurred_at=event.occurred_at,
                lead_id=lead_public_id,
                outreach_message_id=message_public_id,
                metadata=event.metadata_json,
            )
            for event, lead_public_id, message_public_id in self.repository.list_events(
                db, campaign_id
            )
        ]

    def _record_event(
        self,
        db: Session,
        *,
        workspace_id: int,
        campaign: Campaign,
        event_type: str,
        metadata: dict[str, object] | None,
        lead: Lead | None = None,
        message: OutreachMessage | None = None,
    ) -> None:
        self.repository.add_event(
            db,
            OutreachEvent(
                workspace_id=workspace_id,
                campaign_id=campaign.id,
                lead_id=lead.id if lead is not None else None,
                outreach_message_id=message.id if message is not None else None,
                event_type=event_type,
                occurred_at=datetime.now(tz=UTC),
                metadata_json=metadata,
            ),
        )

    def _outreach_tone(self, tone: str) -> OutreachTone:
        try:
            return OutreachTone(tone)
        except ValueError:
            return OutreachTone.CONSULTATIVE
