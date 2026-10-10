from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.error_codes import ErrorCodes
from app.core.errors import ConflictError, NotFoundError
from app.modules.audit_logs.service import AuditLogService
from app.modules.auth.permissions import assert_workspace_permission
from app.modules.proposals.models import ProposalBrand
from app.modules.proposals.schemas import (
    BrandCreateRequest,
    BrandFields,
    BrandListResponse,
    BrandResponse,
    BrandTemplateListResponse,
    BrandTemplateResponse,
    BrandUpdateRequest,
)
from app.modules.proposals.templates import (
    BRAND_TEMPLATES,
    DEFAULT_TEMPLATE_KEY,
    template_values,
)
from app.modules.users.models import User, Workspace


class ProposalBrandNotFoundError(NotFoundError):
    code = ErrorCodes.PROPOSAL_BRAND_NOT_FOUND


class ProposalBrandConflictError(ConflictError):
    code = ErrorCodes.PROPOSAL_BRAND_CONFLICT


#: The fields of a brand a document is rendered from (and frozen on send).
BRAND_FIELDS: tuple[str, ...] = tuple(BrandFields.model_fields)


def brand_response(brand: ProposalBrand) -> BrandResponse:
    return BrandResponse(
        public_id=brand.public_id,
        is_default=brand.is_default,
        archived=brand.archived_at is not None,
        **{field: getattr(brand, field) for field in BRAND_FIELDS},
    )


def brand_snapshot(brand: ProposalBrand) -> dict[str, Any]:
    return brand_response(brand).model_dump(mode="json")


class ProposalBrandService:
    """Each workspace designs its own proposal brands.

    Anyone who can view leads can see and use the brands; only workspace
    managers (owner/admin) can create, change or archive them. A workspace
    always has at least one active brand: a neutral one named after the
    workspace is created the first time it is needed.
    """

    def __init__(self) -> None:
        self.audit_logs = AuditLogService()

    # -- Reads --------------------------------------------------------------

    def list_brands(
        self,
        db: Session,
        *,
        workspace_id: int,
        current_user: User,
        include_archived: bool = False,
    ) -> BrandListResponse:
        assert_workspace_permission(
            current_user.role, "leads:view", message="You cannot view proposal brands."
        )
        self.ensure_default(db, workspace_id=workspace_id, current_user=current_user)
        query = select(ProposalBrand).where(ProposalBrand.workspace_id == workspace_id)
        if not include_archived:
            query = query.where(ProposalBrand.archived_at.is_(None))
        query = query.order_by(ProposalBrand.is_default.desc(), ProposalBrand.name, ProposalBrand.id)
        return BrandListResponse(items=[brand_response(b) for b in db.scalars(query)])

    def list_templates(
        self, db: Session, *, workspace_id: int, current_user: User
    ) -> BrandTemplateListResponse:
        assert_workspace_permission(
            current_user.role, "leads:view", message="You cannot view proposal brands."
        )
        workspace_name = self._workspace_name(db, workspace_id)
        return BrandTemplateListResponse(
            items=[
                BrandTemplateResponse(
                    key=template.key,
                    values=BrandFields(**template_values(template, workspace_name)),
                )
                for template in BRAND_TEMPLATES.values()
            ]
        )

    def get(
        self, db: Session, *, workspace_id: int, brand_public_id: str, current_user: User
    ) -> BrandResponse:
        assert_workspace_permission(
            current_user.role, "leads:view", message="You cannot view proposal brands."
        )
        return brand_response(self._get_or_raise(db, workspace_id, brand_public_id))

    def resolve_for_use(
        self,
        db: Session,
        *,
        workspace_id: int,
        current_user: User,
        brand_public_id: str | None,
    ) -> ProposalBrand:
        """The brand a new or edited proposal uses: the one asked for if it
        is active, or the workspace default when none is named."""
        if not brand_public_id:
            return self.ensure_default(db, workspace_id=workspace_id, current_user=current_user)
        brand = self._get_or_raise(db, workspace_id, brand_public_id)
        if brand.archived_at is not None:
            raise ProposalBrandConflictError(
                f"The brand '{brand.name}' is archived. Choose an active brand."
            )
        return brand

    def find_active(self, db: Session, *, workspace_id: int, reference: str) -> ProposalBrand | None:
        """Look up an active brand by public id or (case-insensitive) name —
        how the copilot names a brand."""
        reference = reference.strip()
        if not reference:
            return None
        return db.scalar(
            select(ProposalBrand)
            .where(
                ProposalBrand.workspace_id == workspace_id,
                ProposalBrand.archived_at.is_(None),
                (ProposalBrand.public_id == reference)
                | (func.lower(ProposalBrand.name) == reference.lower()),
            )
            .order_by(ProposalBrand.is_default.desc(), ProposalBrand.id)
            .limit(1)
        )

    def active_names(self, db: Session, *, workspace_id: int) -> list[str]:
        return list(
            db.scalars(
                select(ProposalBrand.name)
                .where(
                    ProposalBrand.workspace_id == workspace_id,
                    ProposalBrand.archived_at.is_(None),
                )
                .order_by(ProposalBrand.name)
            )
        )

    # -- Writes -------------------------------------------------------------

    def ensure_default(
        self, db: Session, *, workspace_id: int, current_user: User | None
    ) -> ProposalBrand:
        """Return the workspace's default brand, creating a neutral one named
        after the workspace when it has no active brand at all."""
        active = list(
            db.scalars(
                select(ProposalBrand)
                .where(
                    ProposalBrand.workspace_id == workspace_id,
                    ProposalBrand.archived_at.is_(None),
                )
                .order_by(ProposalBrand.is_default.desc(), ProposalBrand.id)
            )
        )
        if active:
            brand = active[0]
            if not brand.is_default:
                brand.is_default = True
                db.add(brand)
                db.commit()
                db.refresh(brand)
            return brand
        values = template_values(
            BRAND_TEMPLATES[DEFAULT_TEMPLATE_KEY], self._workspace_name(db, workspace_id)
        )
        brand = ProposalBrand(
            workspace_id=workspace_id,
            is_default=True,
            created_by_user_id=current_user.id if current_user else None,
            **values,
        )
        db.add(brand)
        db.commit()
        db.refresh(brand)
        return brand

    def create(
        self,
        db: Session,
        *,
        workspace_id: int,
        payload: BrandCreateRequest,
        current_user: User,
    ) -> BrandResponse:
        self._assert_can_manage(current_user)
        values = payload.model_dump(exclude={"is_default"})
        values["default_milestones"] = [m.model_dump() for m in payload.default_milestones]
        has_default = db.scalar(
            select(func.count(ProposalBrand.id)).where(
                ProposalBrand.workspace_id == workspace_id,
                ProposalBrand.archived_at.is_(None),
                ProposalBrand.is_default.is_(True),
            )
        )
        make_default = payload.is_default or not has_default
        if make_default:
            self._clear_default(db, workspace_id)
        brand = ProposalBrand(
            workspace_id=workspace_id,
            is_default=make_default,
            created_by_user_id=current_user.id,
            **values,
        )
        db.add(brand)
        db.commit()
        db.refresh(brand)
        self._audit(db, brand, current_user, "proposal_brand.created", f"Created brand {brand.name}.")
        return brand_response(brand)

    def update(
        self,
        db: Session,
        *,
        workspace_id: int,
        brand_public_id: str,
        payload: BrandUpdateRequest,
        current_user: User,
    ) -> BrandResponse:
        self._assert_can_manage(current_user)
        brand = self._get_or_raise(db, workspace_id, brand_public_id)
        changes = payload.model_dump(exclude_unset=True)
        archived = changes.pop("archived", None)
        for field, value in changes.items():
            if value is None:
                if field == "logo_data_url":
                    brand.logo_data_url = None
                continue
            if field == "default_milestones":
                value = [m.model_dump() for m in payload.default_milestones or []]
            setattr(brand, field, value)

        event = "proposal_brand.updated"
        if archived is True and brand.archived_at is None:
            self._assert_not_last_active(db, brand)
            brand.archived_at = datetime.now(tz=UTC)
            event = "proposal_brand.archived"
            if brand.is_default:
                brand.is_default = False
                db.add(brand)
                db.flush()
                self._promote_another(db, brand)
        elif archived is False and brand.archived_at is not None:
            brand.archived_at = None
            event = "proposal_brand.restored"

        brand.updated_at = datetime.now(tz=UTC)
        db.add(brand)
        db.commit()
        db.refresh(brand)
        self._audit(db, brand, current_user, event, f"Brand {brand.name}: {event.split('.')[-1]}.")
        return brand_response(brand)

    def set_default(
        self, db: Session, *, workspace_id: int, brand_public_id: str, current_user: User
    ) -> BrandResponse:
        self._assert_can_manage(current_user)
        brand = self._get_or_raise(db, workspace_id, brand_public_id)
        if brand.archived_at is not None:
            raise ProposalBrandConflictError("An archived brand cannot be the default.")
        self._clear_default(db, workspace_id)
        brand.is_default = True
        brand.updated_at = datetime.now(tz=UTC)
        db.add(brand)
        db.commit()
        db.refresh(brand)
        self._audit(
            db, brand, current_user, "proposal_brand.default", f"{brand.name} is now the default."
        )
        return brand_response(brand)

    # -- Helpers ------------------------------------------------------------

    @staticmethod
    def _workspace_name(db: Session, workspace_id: int) -> str:
        workspace = db.get(Workspace, workspace_id)
        return workspace.name if workspace else ""

    @staticmethod
    def _clear_default(db: Session, workspace_id: int) -> None:
        db.execute(
            update(ProposalBrand)
            .where(ProposalBrand.workspace_id == workspace_id, ProposalBrand.is_default.is_(True))
            .values(is_default=False)
        )

    @staticmethod
    def _assert_not_last_active(db: Session, brand: ProposalBrand) -> None:
        others = db.scalar(
            select(func.count(ProposalBrand.id)).where(
                ProposalBrand.workspace_id == brand.workspace_id,
                ProposalBrand.archived_at.is_(None),
                ProposalBrand.id != brand.id,
            )
        )
        if not others:
            raise ProposalBrandConflictError(
                "A workspace needs at least one active brand. Create another before archiving this one."
            )

    @staticmethod
    def _promote_another(db: Session, brand: ProposalBrand) -> None:
        successor = db.scalar(
            select(ProposalBrand)
            .where(
                ProposalBrand.workspace_id == brand.workspace_id,
                ProposalBrand.archived_at.is_(None),
                ProposalBrand.id != brand.id,
            )
            .order_by(ProposalBrand.id)
            .limit(1)
        )
        if successor is not None:
            successor.is_default = True
            db.add(successor)

    @staticmethod
    def _get_or_raise(db: Session, workspace_id: int, public_id: str) -> ProposalBrand:
        brand = db.scalar(
            select(ProposalBrand).where(
                ProposalBrand.public_id == public_id, ProposalBrand.workspace_id == workspace_id
            )
        )
        if brand is None:
            raise ProposalBrandNotFoundError("Proposal brand was not found.")
        return brand

    @staticmethod
    def _assert_can_manage(current_user: User) -> None:
        assert_workspace_permission(
            current_user.role,
            "workspace:manage",
            message="Only workspace owners and admins can change proposal brands.",
        )

    def _audit(
        self, db: Session, brand: ProposalBrand, current_user: User, event: str, details: str
    ) -> None:
        self.audit_logs.record(
            db,
            workspace_id=brand.workspace_id,
            actor_user_id=current_user.id,
            event_name=event,
            details=details,
        )
