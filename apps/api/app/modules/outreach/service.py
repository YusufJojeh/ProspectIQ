from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.modules.ai_analysis.models import AIAnalysisSnapshot
from app.modules.ai_analysis.repository import AIAnalysisRepository
from app.modules.ai_analysis.schemas import LeadAnalysisResult
from app.modules.ai_analysis.service import AIAnalysisService
from app.modules.audit_logs.service import AuditLogService
from app.modules.leads.models import Lead
from app.modules.leads.repository import LeadsRepository
from app.modules.outreach.models import OutreachMessage
from app.modules.outreach.repository import OutreachRepository
from app.modules.outreach.schemas import (
    LatestOutreachResponse,
    OutreachDraftResponse,
    OutreachGenerateRequest,
    OutreachMessageResult,
    OutreachMessageUpdateRequest,
)
from app.modules.users.models import User
from app.shared.enums.jobs import OutreachTone


class OutreachGenerationService:
    def __init__(self) -> None:
        self.repository = OutreachRepository()
        self.leads_repository = LeadsRepository()
        self.analysis_repository = AIAnalysisRepository()
        self.analysis_service = AIAnalysisService()
        self.audit_logs = AuditLogService()

    def generate(
        self,
        db: Session,
        *,
        lead: Lead,
        snapshot: AIAnalysisSnapshot,
        analysis: LeadAnalysisResult,
        created_by_user_id: int,
        tone: OutreachTone,
        regenerate: bool = False,
    ) -> OutreachMessageResult:
        existing = self.repository.get_by_snapshot_id(db, snapshot.id, tone=tone.value)
        if existing is not None and not regenerate:
            return OutreachMessageResult(
                subject=existing.edited_subject or existing.subject,
                message=existing.edited_message or existing.message,
                tone=OutreachTone(existing.tone),
            )

        subject, message = self._apply_tone(
            tone=tone,
            company_name=lead.company_name,
            base_subject=analysis.outreach_subject,
            base_message=analysis.outreach_message,
        )
        saved = self.repository.add(
            db,
            OutreachMessage(
                lead_id=lead.id,
                ai_analysis_snapshot_id=snapshot.id,
                subject=subject,
                message=message,
                tone=tone.value,
                version_number=self.repository.get_next_version_number(db, lead.id),
                created_by_user_id=created_by_user_id,
            ),
        )
        return OutreachMessageResult(
            subject=saved.subject,
            message=saved.message,
            tone=OutreachTone(saved.tone),
        )

    def get_latest_for_lead(
        self,
        db: Session,
        *,
        workspace_id: int,
        lead_public_id: str,
    ) -> LatestOutreachResponse:
        lead = self._get_lead_or_raise(db, workspace_id=workspace_id, lead_public_id=lead_public_id)
        message = self.repository.get_latest_by_lead(db, lead.id)
        if message is None:
            return LatestOutreachResponse(lead_id=lead.public_id, message=None)
        return LatestOutreachResponse(
            lead_id=lead.public_id,
            message=self._to_response(db, lead_public_id=lead.public_id, message=message),
        )

    def generate_for_lead(
        self,
        db: Session,
        *,
        workspace_id: int,
        lead_public_id: str,
        current_user: User,
        payload: OutreachGenerateRequest,
    ) -> OutreachDraftResponse:
        lead, snapshot, analysis = self.analysis_service.prepare_analysis_for_lead(
            db,
            workspace_id=workspace_id,
            lead_public_id=lead_public_id,
            created_by_user_id=current_user.id,
        )
        self.generate(
            db,
            lead=lead,
            snapshot=snapshot,
            analysis=analysis,
            created_by_user_id=current_user.id,
            tone=payload.tone,
            regenerate=payload.regenerate,
        )
        message = self.repository.get_latest_by_lead(db, lead.id)
        if message is None:
            raise NotFoundError("Outreach draft was not found.")
        self.audit_logs.record(
            db,
            workspace_id=workspace_id,
            actor_user_id=current_user.id,
            event_name="lead.outreach_generated",
            details=(
                f"Generated outreach draft v{message.version_number} "
                f"({message.tone}) for lead {lead.public_id}."
            ),
        )
        return self._to_response(db, lead_public_id=lead.public_id, message=message)

    def update_draft(
        self,
        db: Session,
        *,
        workspace_id: int,
        message_public_id: str,
        payload: OutreachMessageUpdateRequest,
        current_user: User,
    ) -> OutreachDraftResponse:
        message = self.repository.get_by_public_id(db, message_public_id)
        if message is None:
            raise NotFoundError("Outreach draft was not found.")
        lead = self._get_lead_by_id_or_raise(db, workspace_id=workspace_id, lead_id=message.lead_id)
        message.edited_subject = payload.subject
        message.edited_message = payload.message
        message.updated_at = datetime.now(tz=UTC)
        saved = self.repository.save(db, message)
        self.audit_logs.record(
            db,
            workspace_id=workspace_id,
            actor_user_id=current_user.id,
            event_name="lead.outreach_updated",
            details=(
                f"Updated outreach draft {saved.public_id} "
                f"(v{saved.version_number}, {saved.tone}) for lead {lead.public_id}."
            ),
        )
        return self._to_response(db, lead_public_id=lead.public_id, message=saved)

    def _get_lead_or_raise(
        self,
        db: Session,
        *,
        workspace_id: int,
        lead_public_id: str,
    ) -> Lead:
        lead = self.leads_repository.get_by_public_id(db, lead_public_id)
        if lead is None or lead.workspace_id != workspace_id:
            raise NotFoundError("Lead was not found.")
        return lead

    def _get_lead_by_id_or_raise(
        self,
        db: Session,
        *,
        workspace_id: int,
        lead_id: int,
    ) -> Lead:
        lead = db.get(Lead, lead_id)
        if lead is None or lead.workspace_id != workspace_id:
            raise NotFoundError("Lead was not found.")
        return lead

    def _to_response(
        self,
        db: Session,
        *,
        lead_public_id: str,
        message: OutreachMessage,
    ) -> OutreachDraftResponse:
        snapshot = self.analysis_repository.get_snapshot_by_id(db, message.ai_analysis_snapshot_id)
        if snapshot is None:
            raise NotFoundError("Analysis snapshot was not found for the outreach draft.")
        subject = message.edited_subject or message.subject
        body = message.edited_message or message.message
        return OutreachDraftResponse(
            public_id=message.public_id,
            lead_id=lead_public_id,
            ai_analysis_snapshot_public_id=snapshot.public_id,
            subject=subject,
            message=body,
            tone=OutreachTone(message.tone),
            version_number=message.version_number,
            generated_subject=message.subject,
            generated_message=message.message,
            has_manual_edits=bool(message.edited_subject or message.edited_message),
            created_at=message.created_at,
            updated_at=message.updated_at,
        )

    def _apply_tone(
        self,
        *,
        tone: OutreachTone,
        company_name: str,
        base_subject: str,
        base_message: str,
    ) -> tuple[str, str]:
        if tone == OutreachTone.FORMAL:
            return (
                f"{company_name}: evidence-based growth observations",
                base_message
                + "\n\nIf appropriate, we can share a concise audit and recommended next steps.",
            )
        if tone == OutreachTone.FRIENDLY:
            return (
                f"Quick idea for {company_name}",
                base_message.replace("Hi", "Hello")
                + "\n\nHappy to send a short version if that helps.",
            )
        if tone == OutreachTone.SHORT_PITCH:
            first_line = base_message.splitlines()[0] if base_message.splitlines() else base_message
            return (
                f"{company_name}: quick visibility idea",
                f"{first_line}\n\nWe found two evidence-backed opportunities worth discussing.",
            )
        return base_subject, base_message
