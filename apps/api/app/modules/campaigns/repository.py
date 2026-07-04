from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.modules.campaigns.models import Campaign, CampaignLead, OutreachEvent, SequenceStep
from app.modules.icp.models import IcpProfile
from app.modules.leads.models import Lead
from app.modules.outreach.models import OutreachMessage


class CampaignRepository:
    def list_for_workspace(self, db: Session, workspace_id: int) -> list[Campaign]:
        return list(
            db.scalars(
                select(Campaign)
                .where(Campaign.workspace_id == workspace_id)
                .order_by(Campaign.updated_at.desc(), Campaign.id.desc())
            )
        )

    def get_by_public_id(
        self, db: Session, *, workspace_id: int, campaign_public_id: str
    ) -> Campaign | None:
        return db.scalar(
            select(Campaign).where(
                Campaign.workspace_id == workspace_id,
                Campaign.public_id == campaign_public_id,
            )
        )

    def get_icp_by_public_id(
        self, db: Session, *, workspace_id: int, icp_public_id: str
    ) -> IcpProfile | None:
        return db.scalar(
            select(IcpProfile).where(
                IcpProfile.workspace_id == workspace_id,
                IcpProfile.public_id == icp_public_id,
            )
        )

    def add_campaign(self, db: Session, campaign: Campaign) -> Campaign:
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
        return campaign

    def save_campaign(self, db: Session, campaign: Campaign) -> Campaign:
        campaign.updated_at = datetime.now(tz=UTC)
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
        return campaign

    def list_campaign_leads(self, db: Session, campaign_id: int) -> list[CampaignLead]:
        return list(
            db.scalars(
                select(CampaignLead)
                .where(CampaignLead.campaign_id == campaign_id)
                .order_by(CampaignLead.added_at.desc(), CampaignLead.id.desc())
            )
        )

    def get_campaign_lead(
        self, db: Session, *, campaign_id: int, lead_id: int
    ) -> CampaignLead | None:
        return db.scalar(
            select(CampaignLead).where(
                CampaignLead.campaign_id == campaign_id,
                CampaignLead.lead_id == lead_id,
            )
        )

    def add_campaign_lead(self, db: Session, campaign_lead: CampaignLead) -> CampaignLead:
        db.add(campaign_lead)
        db.commit()
        db.refresh(campaign_lead)
        return campaign_lead

    def save_campaign_lead(self, db: Session, campaign_lead: CampaignLead) -> CampaignLead:
        db.add(campaign_lead)
        db.commit()
        db.refresh(campaign_lead)
        return campaign_lead

    def remove_campaign_lead(self, db: Session, campaign_lead: CampaignLead) -> None:
        db.delete(campaign_lead)
        db.commit()

    def list_sequence_steps(self, db: Session, campaign_id: int) -> list[SequenceStep]:
        return list(
            db.scalars(
                select(SequenceStep)
                .where(SequenceStep.campaign_id == campaign_id)
                .order_by(SequenceStep.step_order.asc(), SequenceStep.id.asc())
            )
        )

    def get_sequence_step(
        self, db: Session, *, campaign_id: int, step_public_id: str
    ) -> SequenceStep | None:
        return db.scalar(
            select(SequenceStep).where(
                SequenceStep.campaign_id == campaign_id,
                SequenceStep.public_id == step_public_id,
            )
        )

    def replace_sequence_steps(self, db: Session, campaign_id: int, steps: list[SequenceStep]) -> None:
        db.execute(delete(SequenceStep).where(SequenceStep.campaign_id == campaign_id))
        db.add_all(steps)
        db.commit()

    def save_sequence_step(self, db: Session, step: SequenceStep) -> SequenceStep:
        step.updated_at = datetime.now(tz=UTC)
        db.add(step)
        db.commit()
        db.refresh(step)
        return step

    def add_event(self, db: Session, event: OutreachEvent) -> OutreachEvent:
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    def list_events(self, db: Session, campaign_id: int) -> list[tuple[OutreachEvent, str | None, str | None]]:
        statement = (
            select(OutreachEvent, Lead.public_id, OutreachMessage.public_id)
            .outerjoin(Lead, Lead.id == OutreachEvent.lead_id)
            .outerjoin(OutreachMessage, OutreachMessage.id == OutreachEvent.outreach_message_id)
            .where(OutreachEvent.campaign_id == campaign_id)
            .order_by(OutreachEvent.occurred_at.desc(), OutreachEvent.id.desc())
        )
        return [
            (event, lead_public_id, message_public_id)
            for event, lead_public_id, message_public_id in db.execute(statement).all()
        ]

    def counts_for_campaigns(self, db: Session, campaign_ids: list[int]) -> dict[int, tuple[int, int]]:
        if not campaign_ids:
            return {}
        lead_rows = db.execute(
            select(CampaignLead.campaign_id, func.count(CampaignLead.id))
            .where(CampaignLead.campaign_id.in_(campaign_ids))
            .group_by(CampaignLead.campaign_id)
        ).all()
        step_rows = db.execute(
            select(SequenceStep.campaign_id, func.count(SequenceStep.id))
            .where(SequenceStep.campaign_id.in_(campaign_ids))
            .group_by(SequenceStep.campaign_id)
        ).all()
        lead_counts = {int(campaign_id): int(count) for campaign_id, count in lead_rows}
        step_counts = {int(campaign_id): int(count) for campaign_id, count in step_rows}
        return {
            campaign_id: (lead_counts.get(campaign_id, 0), step_counts.get(campaign_id, 0))
            for campaign_id in campaign_ids
        }

    def event_metadata(
        self,
        *,
        action: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {"action": action, **(details or {})}
