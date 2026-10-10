"""Add research_runs, research_fact_snapshots, and research_change_events
tables for Delta Intelligence (research-run diffing and change detection).

Revision ID: 0021_research_delta_intelligence
Revises: 0020_research_apify_evidence
Create Date: 2026-09-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op

revision = "0021_research_delta_intelligence"
down_revision = "0020_research_apify_evidence"
branch_labels = None
depends_on = None


def _has_table(bind: sa.engine.Connection, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def upgrade() -> None:
    bind = None if context.is_offline_mode() else op.get_bind()
    if bind is None:
        return

    if not _has_table(bind, "research_runs"):
        op.create_table(
            "research_runs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("public_id", sa.String(length=24), nullable=False, unique=True),
            sa.Column(
                "workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False
            ),
            sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id"), nullable=False),
            sa.Column("depth", sa.String(length=16), nullable=False),
            sa.Column("mode", sa.String(length=16), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("providers_used_json", sa.JSON(), nullable=False),
            sa.Column("evidence_confidence", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("research_coverage", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index(
            "ix_research_runs_lead_created_at", "research_runs", ["lead_id", "created_at"]
        )
        op.create_index("ix_research_runs_workspace_id", "research_runs", ["workspace_id"])
        op.create_index("ix_research_runs_lead_id", "research_runs", ["lead_id"])

    if not _has_table(bind, "research_fact_snapshots"):
        op.create_table(
            "research_fact_snapshots",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "research_run_id", sa.Integer(), sa.ForeignKey("research_runs.id"), nullable=False
            ),
            sa.Column(
                "workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False
            ),
            sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id"), nullable=False),
            sa.Column("claim_type", sa.String(length=64), nullable=False),
            sa.Column("value", sa.String(length=512), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("captured_at", sa.DateTime(), nullable=False),
        )
        op.create_index(
            "ix_research_fact_snapshots_lead_claim",
            "research_fact_snapshots",
            ["lead_id", "claim_type"],
        )
        op.create_index(
            "ix_research_fact_snapshots_run_id", "research_fact_snapshots", ["research_run_id"]
        )
        op.create_index(
            "ix_research_fact_snapshots_workspace_id", "research_fact_snapshots", ["workspace_id"]
        )

    if not _has_table(bind, "research_change_events"):
        op.create_table(
            "research_change_events",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("public_id", sa.String(length=24), nullable=False, unique=True),
            sa.Column(
                "workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False
            ),
            sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id"), nullable=False),
            sa.Column(
                "previous_research_run_id",
                sa.Integer(),
                sa.ForeignKey("research_runs.id"),
                nullable=True,
            ),
            sa.Column(
                "current_research_run_id",
                sa.Integer(),
                sa.ForeignKey("research_runs.id"),
                nullable=False,
            ),
            sa.Column("claim_type", sa.String(length=64), nullable=False),
            sa.Column("previous_value", sa.String(length=512), nullable=True),
            sa.Column("new_value", sa.String(length=512), nullable=True),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column("direction", sa.String(length=16), nullable=False),
            sa.Column("significance", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("explanation", sa.Text(), nullable=True),
            sa.Column("triggered_rescore", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index(
            "ix_research_change_events_lead_created_at",
            "research_change_events",
            ["lead_id", "created_at"],
        )
        op.create_index(
            "ix_research_change_events_workspace_id", "research_change_events", ["workspace_id"]
        )
        op.create_index(
            "ix_research_change_events_lead_id", "research_change_events", ["lead_id"]
        )


def downgrade() -> None:
    bind = None if context.is_offline_mode() else op.get_bind()
    if bind is None:
        return
    if _has_table(bind, "research_change_events"):
        op.drop_table("research_change_events")
    if _has_table(bind, "research_fact_snapshots"):
        op.drop_table("research_fact_snapshots")
    if _has_table(bind, "research_runs"):
        op.drop_table("research_runs")
