"""Workspace-owned proposal brands.

Proposals used to name one of two built-in brand presets (`brand_key`).
Each workspace now designs its own brands in `proposal_brands`; the presets
are only starter templates. Existing proposals are moved onto a workspace
brand copied from the preset they used, and a sent proposal's brand is
frozen in `brand_snapshot`.

Revision ID: 0028_proposal_brands
Revises: 0027_proposals
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = "0028_proposal_brands"
down_revision = "0027_proposals"
branch_labels = None
depends_on = None

_MILESTONES = [
    {
        "title": "Discovery & System Design",
        "description": "Workflow mapping, requirements, domain model, contracts, delivery plan.",
    },
    {
        "title": "Core Engineering & Integrations",
        "description": "Backend, APIs, business rules, integrations, staging and tests.",
    },
    {
        "title": "UAT, Launch & Handover",
        "description": "UAT fixes, production release, runbook and handover.",
    },
]

# Frozen copies of the two presets as they were in 0027, so this migration
# does not change if the starter templates in app code change later.
_PRESETS: dict[str, dict[str, Any]] = {
    "yusuf_jojeh": {
        "name": "Yusuf Jojeh",
        "tagline": "Backend & Business Systems Engineer",
        "mark": "YJ",
        "mark_shape": "square",
        "number_prefix": "YJ-Q",
        "signer_label": "Yusuf Mohammad Jojeh",
        "client_signer_label": "Client · Name / role / date",
        "footer_contact": "linkedin.com/in/yusuf-jojeh",
        "paper": "#F5F2EA",
        "ink": "#151719",
        "muted": "#6D7379",
        "line": "#D8D4CB",
        "accent": "#E45D34",
        "accent_secondary": "#9CA6AF",
        "background": "#0A0C0F",
        "radius_px": 8,
        "default_outcome": (
            "Design and deliver a production-ready backend or business system aligned with the "
            "agreed workflow, roles, permissions, integrations, data model, operational "
            "constraints and release scope."
        ),
        "default_commercial_notes": (
            "The first payment reserves the engagement and starts delivery. Remaining invoices "
            "are tied to agreed milestones. Work outside the signed Statement of Work requires "
            "a written Change Request before implementation."
        ),
        "default_validity_notes": (
            "This quotation is valid for 30 days. Taxes, bank fees, paid APIs, hosting, "
            "licenses and external provider fees are excluded unless explicitly listed."
        ),
    },
    "hexaterminal": {
        "name": "HexaTerminal",
        "tagline": "Production Systems Engineering",
        "mark": ">_",
        "mark_shape": "hex",
        "number_prefix": "HXT-Q",
        "signer_label": "For HexaTerminal · Name / role / date",
        "client_signer_label": "For Client · Name / role / date",
        "footer_contact": "sales@hexaterminal.com · www.hexaterminal.com",
        "paper": "#F7F8FA",
        "ink": "#11161D",
        "muted": "#687383",
        "line": "#D9DEE5",
        "accent": "#2D86FF",
        "accent_secondary": "#FF7A1A",
        "background": "#05070A",
        "radius_px": 12,
        "default_outcome": (
            "Design and deliver a production-ready software system aligned with the agreed "
            "workflow, permissions, integrations, data model and release scope."
        ),
        "default_commercial_notes": (
            "20% deposit starts the project. Remaining invoices are issued on the milestones "
            "above. Work outside the signed Statement of Work requires a written Change "
            "Request before implementation."
        ),
        "default_validity_notes": (
            "This quotation is valid for 30 days. Taxes, third-party subscriptions, paid APIs, "
            "hosting and external provider fees are excluded unless explicitly listed."
        ),
    },
}


def upgrade() -> None:
    op.create_table(
        "proposal_brands",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("public_id", sa.String(length=24), nullable=False, unique=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("tagline", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("mark", sa.String(length=8), nullable=False, server_default=""),
        sa.Column("mark_shape", sa.String(length=16), nullable=False, server_default="circle"),
        sa.Column("font_style", sa.String(length=16), nullable=False, server_default="sans"),
        sa.Column(
            "logo_data_url",
            sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql", "mariadb"),
            nullable=True,
        ),
        sa.Column("number_prefix", sa.String(length=16), nullable=False),
        sa.Column("signer_label", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("client_signer_label", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("footer_contact", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("paper", sa.String(length=7), nullable=False),
        sa.Column("ink", sa.String(length=7), nullable=False),
        sa.Column("muted", sa.String(length=7), nullable=False),
        sa.Column("line", sa.String(length=7), nullable=False),
        sa.Column("accent", sa.String(length=7), nullable=False),
        sa.Column("accent_secondary", sa.String(length=7), nullable=False),
        sa.Column("background", sa.String(length=7), nullable=False),
        sa.Column("radius_px", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("default_currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("validity_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("default_outcome", sa.Text(), nullable=False),
        sa.Column("default_commercial_notes", sa.Text(), nullable=False),
        sa.Column("default_validity_notes", sa.Text(), nullable=False),
        sa.Column("default_milestones", sa.JSON(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_proposal_brands_workspace_id", "proposal_brands", ["workspace_id"])
    op.create_index(
        "ix_proposal_brands_workspace_archived", "proposal_brands", ["workspace_id", "archived_at"]
    )

    with op.batch_alter_table("proposals") as batch:
        batch.add_column(sa.Column("brand_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("brand_snapshot", sa.JSON(), nullable=True))

    _backfill()

    with op.batch_alter_table("proposals") as batch:
        batch.alter_column("brand_id", existing_type=sa.Integer(), nullable=False)
        batch.create_foreign_key(
            "fk_proposals_brand_id_proposal_brands", "proposal_brands", ["brand_id"], ["id"]
        )
        batch.create_index("ix_proposals_brand_id", ["brand_id"])
        batch.drop_column("brand_key")


def _backfill() -> None:
    bind = op.get_bind()
    pairs = bind.execute(
        sa.text("SELECT DISTINCT workspace_id, brand_key FROM proposals ORDER BY workspace_id")
    ).all()
    now = datetime.now(tz=UTC).replace(tzinfo=None)
    brands = sa.table(
        "proposal_brands",
        *(
            sa.column(name)
            for name in (
                "public_id",
                "workspace_id",
                "name",
                "tagline",
                "mark",
                "mark_shape",
                "font_style",
                "number_prefix",
                "signer_label",
                "client_signer_label",
                "footer_contact",
                "paper",
                "ink",
                "muted",
                "line",
                "accent",
                "accent_secondary",
                "background",
                "radius_px",
                "default_currency",
                "validity_days",
                "default_outcome",
                "default_commercial_notes",
                "default_validity_notes",
                "is_default",
                "created_at",
                "updated_at",
            )
        ),
        sa.column("default_milestones", sa.JSON()),
    )
    seen_default: set[int] = set()
    for index, (workspace_id, brand_key) in enumerate(pairs):
        preset = _PRESETS.get(brand_key) or _PRESETS["hexaterminal"]
        public_id = f"pbrand_m28{index:09d}"
        bind.execute(
            brands.insert().values(
                public_id=public_id,
                workspace_id=workspace_id,
                font_style="sans",
                default_currency="USD",
                validity_days=30,
                default_milestones=_MILESTONES,
                is_default=workspace_id not in seen_default,
                created_at=now,
                updated_at=now,
                **preset,
            )
        )
        seen_default.add(workspace_id)
        brand_id = bind.execute(
            sa.text("SELECT id FROM proposal_brands WHERE public_id = :public_id"),
            {"public_id": public_id},
        ).scalar_one()
        bind.execute(
            sa.text(
                "UPDATE proposals SET brand_id = :brand_id "
                "WHERE workspace_id = :workspace_id AND brand_key = :brand_key"
            ),
            {"brand_id": brand_id, "workspace_id": workspace_id, "brand_key": brand_key},
        )
        snapshot = {
            "public_id": public_id,
            "is_default": False,
            "archived": False,
            "font_style": "sans",
            "logo_data_url": None,
            "default_currency": "USD",
            "validity_days": 30,
            "default_milestones": _MILESTONES,
            **preset,
        }
        bind.execute(
            sa.text(
                "UPDATE proposals SET brand_snapshot = :snapshot "
                "WHERE workspace_id = :workspace_id AND brand_key = :brand_key "
                "AND status IN ('sent', 'accepted', 'declined')"
            ),
            {
                "snapshot": json.dumps(snapshot),
                "workspace_id": workspace_id,
                "brand_key": brand_key,
            },
        )


def downgrade() -> None:
    with op.batch_alter_table("proposals") as batch:
        batch.add_column(
            sa.Column("brand_key", sa.String(length=32), nullable=False, server_default="hexaterminal")
        )
    op.execute(
        "UPDATE proposals SET brand_key = 'yusuf_jojeh' WHERE brand_id IN "
        "(SELECT id FROM proposal_brands WHERE number_prefix = 'YJ-Q')"
    )
    with op.batch_alter_table("proposals") as batch:
        batch.drop_index("ix_proposals_brand_id")
        batch.drop_constraint("fk_proposals_brand_id_proposal_brands", type_="foreignkey")
        batch.drop_column("brand_snapshot")
        batch.drop_column("brand_id")
    op.drop_index("ix_proposal_brands_workspace_archived", table_name="proposal_brands")
    op.drop_index("ix_proposal_brands_workspace_id", table_name="proposal_brands")
    op.drop_table("proposal_brands")
