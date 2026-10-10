from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.utils.identifiers import new_public_id


class ProposalBrand(Base):
    """One of a workspace's own proposal identities: name, mark or logo,
    colours, numbering, signatures and the default commercial copy.

    Brands are archived, never deleted, so every proposal keeps the identity
    it was written in. A sent proposal additionally freezes a snapshot of
    its brand, so later edits never change a document a client received.
    """

    __tablename__ = "proposal_brands"
    __table_args__ = (Index("ix_proposal_brands_workspace_archived", "workspace_id", "archived_at"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(24), unique=True, default=lambda: new_public_id("pbrand")
    )
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    tagline: Mapped[str] = mapped_column(String(160), default="")
    mark: Mapped[str] = mapped_column(String(8), default="")
    mark_shape: Mapped[str] = mapped_column(String(16), default="circle")
    font_style: Mapped[str] = mapped_column(String(16), default="sans")
    logo_data_url: Mapped[str | None] = mapped_column(
        Text().with_variant(MEDIUMTEXT(), "mysql", "mariadb"), nullable=True
    )
    number_prefix: Mapped[str] = mapped_column(String(16))
    signer_label: Mapped[str] = mapped_column(String(160), default="")
    client_signer_label: Mapped[str] = mapped_column(String(160), default="")
    footer_contact: Mapped[str] = mapped_column(String(255), default="")
    paper: Mapped[str] = mapped_column(String(7))
    ink: Mapped[str] = mapped_column(String(7))
    muted: Mapped[str] = mapped_column(String(7))
    line: Mapped[str] = mapped_column(String(7))
    accent: Mapped[str] = mapped_column(String(7))
    accent_secondary: Mapped[str] = mapped_column(String(7))
    background: Mapped[str] = mapped_column(String(7))
    radius_px: Mapped[int] = mapped_column(Integer(), default=8)
    default_currency: Mapped[str] = mapped_column(String(3), default="USD")
    validity_days: Mapped[int] = mapped_column(Integer(), default=30)
    default_outcome: Mapped[str] = mapped_column(Text(), default="")
    default_commercial_notes: Mapped[str] = mapped_column(Text(), default="")
    default_validity_notes: Mapped[str] = mapped_column(Text(), default="")
    #: [{title, description}] — the milestone lines a new proposal starts with.
    default_milestones: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    is_default: Mapped[bool] = mapped_column(Boolean(), default=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))


class Proposal(Base):
    """A priced proposal / quotation for one lead, in one of the workspace's brands.

    Money is stored in minor units inside `milestones`; totals, deposit and
    shares are always derived from those amounts and never stored, so a
    document can never show a total that disagrees with its own lines.
    """

    __tablename__ = "proposals"
    __table_args__ = (
        UniqueConstraint("workspace_id", "number", name="uq_proposals_workspace_number"),
        Index("ix_proposals_workspace_status", "workspace_id", "status"),
        Index("ix_proposals_lead_created_at", "lead_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(24), unique=True, default=lambda: new_public_id("prop")
    )
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    number: Mapped[str] = mapped_column(String(32))
    brand_id: Mapped[int] = mapped_column(ForeignKey("proposal_brands.id"), index=True)
    #: The brand as it was when the proposal was sent; null until then.
    brand_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    language: Mapped[str] = mapped_column(String(8), default="en")
    status: Mapped[str] = mapped_column(String(16), default="draft")
    title: Mapped[str] = mapped_column(String(255), default="")
    client_company: Mapped[str] = mapped_column(String(255), default="")
    client_contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    client_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    client_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    issue_date: Mapped[date] = mapped_column(Date())
    valid_until: Mapped[date] = mapped_column(Date())
    outcome: Mapped[str] = mapped_column(Text(), default="")
    milestones: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    commercial_notes: Mapped[str] = mapped_column(Text(), default="")
    validity_notes: Mapped[str] = mapped_column(Text(), default="")
    sender_contact: Mapped[str] = mapped_column(String(255), default="")
    #: Where the prices came from, when the copilot drafted it: the cited
    #: pricing guidance, shown to the approver and kept for audit.
    pricing_basis: Mapped[str | None] = mapped_column(Text(), nullable=True)
    source_agent_run_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))
