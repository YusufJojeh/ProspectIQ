"""Add campaigns, sequence steps, and outreach events.

Revision ID: 0016_campaign_sequences
Revises: 0015_platform_admin_role
Create Date: 2026-06-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op

revision = "0016_campaign_sequences"
down_revision = "0015_platform_admin_role"
branch_labels = None
depends_on = None


def _has_table(bind: sa.engine.Connection, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def upgrade() -> None:
    bind = None if context.is_offline_mode() else op.get_bind()

    if bind is None or not _has_table(bind, "campaigns"):
        op.create_table(
            "campaigns",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("public_id", sa.String(length=24), nullable=False),
            sa.Column("workspace_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=160), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("icp_profile_id", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(length=24), nullable=False, server_default="draft"),
            sa.Column("created_by_user_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["icp_profile_id"], ["icp_profiles.id"]),
            sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("public_id"),
        )
        op.create_index("ix_campaigns_workspace_id", "campaigns", ["workspace_id"])
        op.create_index("ix_campaigns_icp_profile_id", "campaigns", ["icp_profile_id"])
        op.create_index("ix_campaigns_created_by_user_id", "campaigns", ["created_by_user_id"])
        op.create_index("ix_campaigns_workspace_status", "campaigns", ["workspace_id", "status"])

    if bind is None or not _has_table(bind, "campaign_leads"):
        op.create_table(
            "campaign_leads",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("campaign_id", sa.Integer(), nullable=False),
            sa.Column("lead_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=24), nullable=False, server_default="added"),
            sa.Column("added_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
            sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "campaign_id",
                "lead_id",
                name="uq_campaign_leads_campaign_lead",
            ),
        )
        op.create_index("ix_campaign_leads_campaign_id", "campaign_leads", ["campaign_id"])
        op.create_index("ix_campaign_leads_lead_id", "campaign_leads", ["lead_id"])
        op.create_index(
            "ix_campaign_leads_campaign_lead",
            "campaign_leads",
            ["campaign_id", "lead_id"],
        )

    if bind is None or not _has_table(bind, "sequence_steps"):
        op.create_table(
            "sequence_steps",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("public_id", sa.String(length=24), nullable=False),
            sa.Column("campaign_id", sa.Integer(), nullable=False),
            sa.Column("step_order", sa.Integer(), nullable=False),
            sa.Column("channel", sa.String(length=24), nullable=False, server_default="email"),
            sa.Column("delay_days", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("tone", sa.String(length=32), nullable=False, server_default="consultative"),
            sa.Column("language", sa.String(length=8), nullable=False, server_default="en"),
            sa.Column("template_text", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("public_id"),
            sa.UniqueConstraint("campaign_id", "step_order", name="uq_sequence_steps_campaign_order"),
        )
        op.create_index("ix_sequence_steps_campaign_id", "sequence_steps", ["campaign_id"])
        op.create_index(
            "ix_sequence_steps_campaign_order",
            "sequence_steps",
            ["campaign_id", "step_order"],
        )

    if bind is None or not _has_table(bind, "outreach_events"):
        op.create_table(
            "outreach_events",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("public_id", sa.String(length=24), nullable=False),
            sa.Column("workspace_id", sa.Integer(), nullable=False),
            sa.Column("campaign_id", sa.Integer(), nullable=True),
            sa.Column("lead_id", sa.Integer(), nullable=True),
            sa.Column("outreach_message_id", sa.Integer(), nullable=True),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column("occurred_at", sa.DateTime(), nullable=False),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
            sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
            sa.ForeignKeyConstraint(["outreach_message_id"], ["outreach_messages.id"]),
            sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("public_id"),
        )
        op.create_index("ix_outreach_events_workspace_id", "outreach_events", ["workspace_id"])
        op.create_index("ix_outreach_events_campaign_id", "outreach_events", ["campaign_id"])
        op.create_index("ix_outreach_events_lead_id", "outreach_events", ["lead_id"])
        op.create_index(
            "ix_outreach_events_outreach_message_id",
            "outreach_events",
            ["outreach_message_id"],
        )
        op.create_index(
            "ix_outreach_events_workspace_type",
            "outreach_events",
            ["workspace_id", "event_type"],
        )
        op.create_index(
            "ix_outreach_events_campaign_type",
            "outreach_events",
            ["campaign_id", "event_type"],
        )
        op.create_index(
            "ix_outreach_events_lead_type",
            "outreach_events",
            ["lead_id", "event_type"],
        )


def downgrade() -> None:
    op.drop_table("outreach_events")
    op.drop_table("sequence_steps")
    op.drop_table("campaign_leads")
    op.drop_table("campaigns")
