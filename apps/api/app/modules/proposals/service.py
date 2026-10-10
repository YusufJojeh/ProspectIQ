from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.error_codes import ErrorCodes
from app.core.errors import ApiError, ConflictError, NotFoundError
from app.modules.audit_logs.service import AuditLogService
from app.modules.auth.permissions import assert_workspace_permission
from app.modules.leads.models import Lead
from app.modules.leads.repository import LeadsRepository
from app.modules.proposals.brands import BRAND_PRESETS, BrandPreset, get_brand
from app.modules.proposals.documents import (
    EDITABLE_STATUSES,
    STATUS_DRAFT,
    STATUS_READY,
    STATUS_SENT,
    amount_of,
    compute_totals,
    next_number,
    readiness_issues,
    share_pct,
)
from app.modules.proposals.models import Proposal
from app.modules.proposals.schemas import (
    BrandListResponse,
    BrandResponse,
    MilestoneInput,
    MilestoneResponse,
    ProposalCreateRequest,
    ProposalDecisionRequest,
    ProposalListResponse,
    ProposalReadiness,
    ProposalResponse,
    ProposalSummary,
    ProposalTotals,
    ProposalUpdateRequest,
)
from app.modules.users.models import User


class ProposalNotFoundError(NotFoundError):
    code = ErrorCodes.PROPOSAL_NOT_FOUND


class ProposalConflictError(ConflictError):
    code = ErrorCodes.PROPOSAL_CONFLICT


class ProposalNotReadyError(ApiError):
    status_code = 422
    code = ErrorCodes.PROPOSAL_NOT_READY


class ProposalInvalidError(ApiError):
    status_code = 422
    code = ErrorCodes.PROPOSAL_INVALID


#: Optional fields an update may explicitly clear with null.
_CLEARABLE = frozenset({"client_contact_name", "client_email", "client_location"})
_NUMBER_ATTEMPTS = 3


def _today() -> date:
    return datetime.now(tz=UTC).date()


def _brand_response(brand: BrandPreset) -> BrandResponse:
    data = asdict(brand)
    data.pop("default_outcome")
    data.pop("default_commercial_notes")
    data.pop("default_validity_notes")
    data.pop("default_milestones")
    return BrandResponse(**data)


def _require_brand(key: str) -> BrandPreset:
    brand = get_brand(key)
    if brand is None:
        raise ProposalInvalidError(
            f"Unknown proposal brand '{key}'. Use one of: {', '.join(BRAND_PRESETS)}."
        )
    return brand


def _milestones_payload(items: list[MilestoneInput]) -> list[dict[str, Any]]:
    return [
        {"title": item.title, "description": item.description, "amount_minor": item.amount_minor}
        for item in items
    ]


class ProposalService:
    """Proposals are drafted (by a person or an approved copilot action),
    edited, checked for readiness, and then marked ready / sent / decided.

    Nothing here transmits a proposal: "sent" records that a person sent the
    PDF themselves. Every state change is audit-logged.
    """

    def __init__(self) -> None:
        self.leads_repository = LeadsRepository()
        self.audit_logs = AuditLogService()

    # -- Reads --------------------------------------------------------------

    def list_brands(self) -> BrandListResponse:
        return BrandListResponse(items=[_brand_response(b) for b in BRAND_PRESETS.values()])

    def list_proposals(
        self,
        db: Session,
        *,
        workspace_id: int,
        current_user: User,
        lead_public_id: str | None = None,
    ) -> ProposalListResponse:
        assert_workspace_permission(
            current_user.role, "leads:view", message="You cannot view proposals."
        )
        query = (
            select(Proposal, Lead.public_id, Lead.company_name)
            .join(Lead, Lead.id == Proposal.lead_id)
            .where(Proposal.workspace_id == workspace_id)
            .order_by(Proposal.updated_at.desc(), Proposal.id.desc())
            .limit(200)
        )
        if lead_public_id is not None:
            query = query.where(Lead.public_id == lead_public_id)
        today = _today()
        items = [
            ProposalSummary(
                public_id=proposal.public_id,
                number=proposal.number,
                status=proposal.status,
                lead_id=lead_id,
                lead_company_name=company,
                brand_key=proposal.brand_key,
                title=proposal.title,
                client_company=proposal.client_company,
                currency=proposal.currency,
                total_minor=compute_totals(proposal.milestones or []).total_minor,
                valid_until=proposal.valid_until,
                ready=not self._issues(proposal, today),
                updated_at=proposal.updated_at,
            )
            for proposal, lead_id, company in db.execute(query).all()
        ]
        return ProposalListResponse(items=items)

    def get(
        self, db: Session, *, workspace_id: int, proposal_public_id: str, current_user: User
    ) -> ProposalResponse:
        assert_workspace_permission(
            current_user.role, "leads:view", message="You cannot view proposals."
        )
        proposal = self._get_or_raise(db, workspace_id=workspace_id, public_id=proposal_public_id)
        return self.to_response(db, proposal)

    # -- Writes -------------------------------------------------------------

    def create_for_lead(
        self,
        db: Session,
        *,
        workspace_id: int,
        payload: ProposalCreateRequest,
        current_user: User,
    ) -> ProposalResponse:
        self._assert_can_write(current_user)
        lead = self.leads_repository.get_by_public_id_for_workspace(
            db, workspace_id=workspace_id, public_id=payload.lead_id
        )
        if lead is None:
            raise NotFoundError("Lead was not found.")
        brand = _require_brand(payload.brand_key)
        proposal = self.create(
            db,
            workspace_id=workspace_id,
            lead=lead,
            brand=brand,
            language=payload.language,
            current_user=current_user,
        )
        return self.to_response(db, proposal)

    def create(
        self,
        db: Session,
        *,
        workspace_id: int,
        lead: Lead,
        brand: BrandPreset,
        current_user: User,
        language: str = "en",
        title: str | None = None,
        outcome: str | None = None,
        currency: str | None = None,
        validity_days: int | None = None,
        milestones: list[dict[str, Any]] | None = None,
        commercial_notes: str | None = None,
        pricing_basis: str | None = None,
        source_agent_run_id: str | None = None,
    ) -> Proposal:
        """Create a draft prefilled from the lead and the brand's defaults.

        The template milestones arrive unpriced: a default price would be a
        number nobody chose for this client.
        """
        today = _today()
        days = validity_days or brand.validity_days
        lines = (
            milestones
            if milestones is not None
            else [
                {"title": m.title, "description": m.description, "amount_minor": None}
                for m in brand.default_milestones
            ]
        )
        validity_notes = brand.default_validity_notes
        if days != 30:
            validity_notes = validity_notes.replace("30 days", f"{days} days")

        for attempt in range(_NUMBER_ATTEMPTS):
            proposal = Proposal(
                workspace_id=workspace_id,
                lead_id=lead.id,
                number=self._next_number(db, workspace_id=workspace_id, brand=brand, today=today),
                brand_key=brand.key,
                language=language,
                status=STATUS_DRAFT,
                title=title or "",
                client_company=lead.company_name,
                client_email=lead.email,
                client_location=lead.city or None,
                currency=(currency or brand.default_currency).upper(),
                issue_date=today,
                valid_until=today + timedelta(days=days),
                outcome=outcome or brand.default_outcome,
                milestones=lines,
                commercial_notes=commercial_notes or brand.default_commercial_notes,
                validity_notes=validity_notes,
                sender_contact=brand.footer_contact,
                pricing_basis=pricing_basis,
                source_agent_run_id=source_agent_run_id,
                created_by_user_id=current_user.id,
            )
            db.add(proposal)
            try:
                db.commit()
            except IntegrityError:
                # Two drafts raced for the same number; take the next one.
                db.rollback()
                if attempt == _NUMBER_ATTEMPTS - 1:
                    raise ProposalConflictError(
                        "Could not allocate a proposal number. Try again."
                    ) from None
                continue
            db.refresh(proposal)
            break

        self.audit_logs.record(
            db,
            workspace_id=workspace_id,
            actor_user_id=current_user.id,
            event_name="proposal.created",
            details=(
                f"Created proposal {proposal.number} ({brand.name}) for lead {lead.public_id}"
                + (f" from agent run {source_agent_run_id}." if source_agent_run_id else ".")
            ),
        )
        return proposal

    def update(
        self,
        db: Session,
        *,
        workspace_id: int,
        proposal_public_id: str,
        payload: ProposalUpdateRequest,
        current_user: User,
    ) -> ProposalResponse:
        self._assert_can_write(current_user)
        proposal = self._get_or_raise(db, workspace_id=workspace_id, public_id=proposal_public_id)
        if proposal.status not in EDITABLE_STATUSES:
            raise ProposalConflictError(
                f"Proposal {proposal.number} is {proposal.status} and can no longer be edited."
            )

        changes = payload.model_dump(exclude_unset=True)
        for field, value in changes.items():
            if value is None:
                if field in _CLEARABLE:
                    setattr(proposal, field, None)
                continue
            if field == "brand_key":
                _require_brand(value)
            if field == "milestones":
                value = _milestones_payload(payload.milestones or [])
            if field in _CLEARABLE and isinstance(value, str) and not value:
                value = None
            setattr(proposal, field, value)

        if proposal.valid_until <= proposal.issue_date:
            raise ProposalInvalidError("The validity date must be after the issue date.")

        # A ready proposal that changes must be checked again before it is
        # trusted: "ready" means a person reviewed exactly this content.
        if changes and proposal.status == STATUS_READY:
            proposal.status = STATUS_DRAFT
        proposal.updated_at = datetime.now(tz=UTC)
        db.add(proposal)
        db.commit()
        db.refresh(proposal)
        return self.to_response(db, proposal)

    def mark_ready(
        self, db: Session, *, workspace_id: int, proposal_public_id: str, current_user: User
    ) -> ProposalResponse:
        self._assert_can_write(current_user)
        proposal = self._get_or_raise(db, workspace_id=workspace_id, public_id=proposal_public_id)
        if proposal.status not in EDITABLE_STATUSES:
            raise ProposalConflictError(f"Proposal {proposal.number} is already {proposal.status}.")
        issues = self._issues(proposal, _today())
        if issues:
            raise ProposalNotReadyError(
                f"Proposal {proposal.number} is not ready to send: {', '.join(issues)}."
            )
        return self._transition(
            db, proposal, STATUS_READY, current_user, event="proposal.marked_ready"
        )

    def mark_sent(
        self, db: Session, *, workspace_id: int, proposal_public_id: str, current_user: User
    ) -> ProposalResponse:
        self._assert_can_write(current_user)
        proposal = self._get_or_raise(db, workspace_id=workspace_id, public_id=proposal_public_id)
        if proposal.status != STATUS_READY:
            raise ProposalConflictError(
                f"Only a ready proposal can be marked sent; {proposal.number} is {proposal.status}."
            )
        # Re-checked: a ready proposal can expire before anyone sends it.
        issues = self._issues(proposal, _today())
        if issues:
            raise ProposalNotReadyError(
                f"Proposal {proposal.number} is not ready to send: {', '.join(issues)}."
            )
        proposal.sent_at = datetime.now(tz=UTC)
        return self._transition(db, proposal, STATUS_SENT, current_user, event="proposal.sent")

    def record_decision(
        self,
        db: Session,
        *,
        workspace_id: int,
        proposal_public_id: str,
        payload: ProposalDecisionRequest,
        current_user: User,
    ) -> ProposalResponse:
        self._assert_can_write(current_user)
        proposal = self._get_or_raise(db, workspace_id=workspace_id, public_id=proposal_public_id)
        if proposal.status != STATUS_SENT:
            raise ProposalConflictError(
                f"Only a sent proposal can be accepted or declined; {proposal.number} is "
                f"{proposal.status}."
            )
        proposal.decided_at = datetime.now(tz=UTC)
        return self._transition(
            db, proposal, payload.decision, current_user, event=f"proposal.{payload.decision}"
        )

    # -- Helpers ------------------------------------------------------------

    def to_response(self, db: Session, proposal: Proposal) -> ProposalResponse:
        lead = db.get(Lead, proposal.lead_id)
        brand = get_brand(proposal.brand_key) or next(iter(BRAND_PRESETS.values()))
        lines = list(proposal.milestones or [])
        totals = compute_totals(lines)
        issues = self._issues(proposal, _today())
        return ProposalResponse(
            public_id=proposal.public_id,
            number=proposal.number,
            status=proposal.status,  # type: ignore[arg-type]
            lead_id=lead.public_id if lead else "",
            lead_company_name=lead.company_name if lead else "",
            brand=_brand_response(brand),
            language=proposal.language,  # type: ignore[arg-type]
            title=proposal.title,
            client_company=proposal.client_company,
            client_contact_name=proposal.client_contact_name,
            client_email=proposal.client_email,
            client_location=proposal.client_location,
            currency=proposal.currency,
            issue_date=proposal.issue_date,
            valid_until=proposal.valid_until,
            outcome=proposal.outcome,
            milestones=[
                MilestoneResponse(
                    title=str(item.get("title") or ""),
                    description=str(item.get("description") or ""),
                    amount_minor=amount_of(item),
                    share_pct=share_pct(amount_of(item), totals.total_minor),
                )
                for item in lines
            ],
            commercial_notes=proposal.commercial_notes,
            validity_notes=proposal.validity_notes,
            sender_contact=proposal.sender_contact,
            pricing_basis=proposal.pricing_basis,
            source_agent_run_id=proposal.source_agent_run_id,
            totals=ProposalTotals(
                total_minor=totals.total_minor,
                deposit_minor=totals.deposit_minor,
                remaining_minor=totals.remaining_minor,
            ),
            readiness=ProposalReadiness(ready=not issues, issues=issues),
            sent_at=proposal.sent_at,
            decided_at=proposal.decided_at,
            created_at=proposal.created_at,
            updated_at=proposal.updated_at,
        )

    @staticmethod
    def _issues(proposal: Proposal, today: date) -> list[str]:
        return readiness_issues(
            title=proposal.title,
            client_company=proposal.client_company,
            client_email=proposal.client_email,
            client_contact_name=proposal.client_contact_name,
            client_location=proposal.client_location,
            outcome=proposal.outcome,
            milestones=list(proposal.milestones or []),
            commercial_notes=proposal.commercial_notes,
            validity_notes=proposal.validity_notes,
            issue_date=proposal.issue_date,
            valid_until=proposal.valid_until,
            today=today,
        )

    def _transition(
        self, db: Session, proposal: Proposal, status: str, current_user: User, *, event: str
    ) -> ProposalResponse:
        proposal.status = status
        proposal.updated_at = datetime.now(tz=UTC)
        db.add(proposal)
        db.commit()
        db.refresh(proposal)
        self.audit_logs.record(
            db,
            workspace_id=proposal.workspace_id,
            actor_user_id=current_user.id,
            event_name=event,
            details=f"Proposal {proposal.number} is now {status}.",
        )
        return self.to_response(db, proposal)

    @staticmethod
    def _next_number(db: Session, *, workspace_id: int, brand: BrandPreset, today: date) -> str:
        stem = f"{brand.number_prefix}-{today.year}-"
        existing = list(
            db.scalars(
                select(Proposal.number).where(
                    Proposal.workspace_id == workspace_id, Proposal.number.like(f"{stem}%")
                )
            )
        )
        return next_number(brand.number_prefix, today.year, existing)

    @staticmethod
    def _get_or_raise(db: Session, *, workspace_id: int, public_id: str) -> Proposal:
        proposal = db.scalar(
            select(Proposal).where(
                Proposal.public_id == public_id, Proposal.workspace_id == workspace_id
            )
        )
        if proposal is None:
            raise ProposalNotFoundError("Proposal was not found.")
        return proposal

    @staticmethod
    def _assert_can_write(current_user: User) -> None:
        assert_workspace_permission(
            current_user.role, "outreach:manage", message="You cannot edit proposals."
        )
