"""Add CRM pipelines, deals, and activities.

Revision ID: 0017_crm_pipeline
Revises: 0016_campaign_sequences
Create Date: 2026-06-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op

revision = "0017_crm_pipeline"
down_revision = "0016_campaign_sequences"
branch_labels = None
depends_on = None


def _has_table(bind: sa.engine.Connection, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def upgrade() -> None:
    bind = None if context.is_offline_mode() else op.get_bind()

    if bind is None or not _has_table(bind, "crm_pipelines"):
        op.create_table(
            "crm_pipelines",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("public_id", sa.String(length=24), nullable=False),
            sa.Column("workspace_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=160), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_by_user_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("public_id"),
            sa.UniqueConstraint("workspace_id", "name", name="uq_crm_pipelines_workspace_name"),
        )
        op.create_index("ix_crm_pipelines_workspace_id", "crm_pipelines", ["workspace_id"])
        op.create_index(
            "ix_crm_pipelines_created_by_user_id",
            "crm_pipelines",
            ["created_by_user_id"],
        )
        op.create_index(
            "ix_crm_pipelines_workspace_default",
            "crm_pipelines",
            ["workspace_id", "is_default"],
        )

    if bind is None or not _has_table(bind, "crm_stages"):
        op.create_table(
            "crm_stages",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("public_id", sa.String(length=24), nullable=False),
            sa.Column("workspace_id", sa.Integer(), nullable=False),
            sa.Column("pipeline_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.Column("probability", sa.Integer(), nullable=False, server_default="10"),
            sa.Column("color", sa.String(length=32), nullable=False, server_default="slate"),
            sa.Column("stage_type", sa.String(length=24), nullable=False, server_default="open"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["pipeline_id"], ["crm_pipelines.id"]),
            sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("public_id"),
            sa.UniqueConstraint("pipeline_id", "position", name="uq_crm_stages_pipeline_position"),
        )
        op.create_index("ix_crm_stages_workspace_id", "crm_stages", ["workspace_id"])
        op.create_index("ix_crm_stages_pipeline_id", "crm_stages", ["pipeline_id"])
        op.create_index(
            "ix_crm_stages_pipeline_position",
            "crm_stages",
            ["pipeline_id", "position"],
        )

    if bind is None or not _has_table(bind, "crm_deals"):
        op.create_table(
            "crm_deals",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("public_id", sa.String(length=24), nullable=False),
            sa.Column("workspace_id", sa.Integer(), nullable=False),
            sa.Column("pipeline_id", sa.Integer(), nullable=False),
            sa.Column("stage_id", sa.Integer(), nullable=False),
            sa.Column("lead_id", sa.Integer(), nullable=False),
            sa.Column("campaign_id", sa.Integer(), nullable=True),
            sa.Column("owner_user_id", sa.Integer(), nullable=True),
            sa.Column("title", sa.String(length=180), nullable=False),
            sa.Column("value_amount", sa.Numeric(precision=12, scale=2), nullable=True),
            sa.Column("currency", sa.String(length=8), nullable=False, server_default="USD"),
            sa.Column("probability", sa.Integer(), nullable=False, server_default="10"),
            sa.Column("status", sa.String(length=24), nullable=False, server_default="open"),
            sa.Column("lost_reason", sa.String(length=255), nullable=True),
            sa.Column("expected_close_date", sa.DateTime(), nullable=True),
            sa.Column("next_follow_up_at", sa.DateTime(), nullable=True),
            sa.Column("last_activity_at", sa.DateTime(), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
            sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["pipeline_id"], ["crm_pipelines.id"]),
            sa.ForeignKeyConstraint(["stage_id"], ["crm_stages.id"]),
            sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("public_id"),
        )
        op.create_index("ix_crm_deals_workspace_id", "crm_deals", ["workspace_id"])
        op.create_index("ix_crm_deals_pipeline_id", "crm_deals", ["pipeline_id"])
        op.create_index("ix_crm_deals_stage_id", "crm_deals", ["stage_id"])
        op.create_index("ix_crm_deals_lead_id", "crm_deals", ["lead_id"])
        op.create_index("ix_crm_deals_campaign_id", "crm_deals", ["campaign_id"])
        op.create_index("ix_crm_deals_owner_user_id", "crm_deals", ["owner_user_id"])
        op.create_index("ix_crm_deals_created_by_user_id", "crm_deals", ["created_by_user_id"])
        op.create_index("ix_crm_deals_workspace_status", "crm_deals", ["workspace_id", "status"])
        op.create_index("ix_crm_deals_pipeline_stage", "crm_deals", ["pipeline_id", "stage_id"])
        op.create_index("ix_crm_deals_lead_status", "crm_deals", ["lead_id", "status"])

    if bind is None or not _has_table(bind, "crm_activities"):
        op.create_table(
            "crm_activities",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("public_id", sa.String(length=24), nullable=False),
            sa.Column("workspace_id", sa.Integer(), nullable=False),
            sa.Column("deal_id", sa.Integer(), nullable=False),
            sa.Column("activity_type", sa.String(length=32), nullable=False),
            sa.Column("title", sa.String(length=180), nullable=False),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("due_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("actor_user_id", sa.Integer(), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["deal_id"], ["crm_deals.id"]),
            sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("public_id"),
        )
        op.create_index("ix_crm_activities_workspace_id", "crm_activities", ["workspace_id"])
        op.create_index("ix_crm_activities_deal_id", "crm_activities", ["deal_id"])
        op.create_index("ix_crm_activities_actor_user_id", "crm_activities", ["actor_user_id"])
        op.create_index("ix_crm_activities_deal_due", "crm_activities", ["deal_id", "due_at"])
        op.create_index(
            "ix_crm_activities_workspace_type",
            "crm_activities",
            ["workspace_id", "activity_type"],
        )


def downgrade() -> None:
    op.drop_table("crm_activities")
    op.drop_table("crm_deals")
    op.drop_table("crm_stages")
    op.drop_table("crm_pipelines")
