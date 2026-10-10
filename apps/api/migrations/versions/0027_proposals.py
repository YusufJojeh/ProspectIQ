"""Proposals / quotations.

Adds the proposals table: a priced, branded proposal for one lead. Money
lives in minor units inside the milestones JSON; totals are derived, never
stored. Purely additive.

Revision ID: 0027_proposals
Revises: 0026_evidence_and_job_dedup
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0027_proposals"
down_revision = "0026_evidence_and_job_dedup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "proposals",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("public_id", sa.String(length=24), nullable=False, unique=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id"), nullable=False),
        sa.Column("number", sa.String(length=32), nullable=False),
        sa.Column("brand_key", sa.String(length=32), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False, server_default="en"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
        sa.Column("title", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("client_company", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("client_contact_name", sa.String(length=255), nullable=True),
        sa.Column("client_email", sa.String(length=320), nullable=True),
        sa.Column("client_location", sa.String(length=255), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("milestones", sa.JSON(), nullable=False),
        sa.Column("commercial_notes", sa.Text(), nullable=False),
        sa.Column("validity_notes", sa.Text(), nullable=False),
        sa.Column("sender_contact", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("pricing_basis", sa.Text(), nullable=True),
        sa.Column("source_agent_run_id", sa.String(length=32), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("workspace_id", "number", name="uq_proposals_workspace_number"),
    )
    op.create_index("ix_proposals_workspace_id", "proposals", ["workspace_id"])
    op.create_index("ix_proposals_lead_id", "proposals", ["lead_id"])
    op.create_index("ix_proposals_created_by_user_id", "proposals", ["created_by_user_id"])
    op.create_index("ix_proposals_workspace_status", "proposals", ["workspace_id", "status"])
    op.create_index("ix_proposals_lead_created_at", "proposals", ["lead_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_proposals_lead_created_at", table_name="proposals")
    op.drop_index("ix_proposals_workspace_status", table_name="proposals")
    op.drop_index("ix_proposals_created_by_user_id", table_name="proposals")
    op.drop_index("ix_proposals_lead_id", table_name="proposals")
    op.drop_index("ix_proposals_workspace_id", table_name="proposals")
    op.drop_table("proposals")
