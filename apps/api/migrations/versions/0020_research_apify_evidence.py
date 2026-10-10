"""Add Apify provenance columns and the research_contradictions table.

Revision ID: 0020_research_apify_evidence
Revises: 0019_repair_scoring_weight_totals
Create Date: 2026-09-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op

revision = "0020_research_apify_evidence"
down_revision = "0019_repair_scoring_weight_totals"
branch_labels = None
depends_on = None


def _has_column(bind: sa.engine.Connection, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _has_table(bind: sa.engine.Connection, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def upgrade() -> None:
    bind = None if context.is_offline_mode() else op.get_bind()
    if bind is None:
        return

    if not _has_column(bind, "provider_normalized_facts", "freshness_score"):
        op.add_column(
            "provider_normalized_facts",
            sa.Column("freshness_score", sa.Float(), nullable=False, server_default="1.0"),
        )
    if not _has_column(bind, "provider_normalized_facts", "actor_run_id"):
        op.add_column(
            "provider_normalized_facts",
            sa.Column("actor_run_id", sa.String(length=64), nullable=True),
        )

    if not _has_table(bind, "research_contradictions"):
        op.create_table(
            "research_contradictions",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False
            ),
            sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id"), nullable=False),
            sa.Column("claim_type", sa.String(length=32), nullable=False),
            sa.Column("values_json", sa.JSON(), nullable=False),
            sa.Column("detected_at", sa.DateTime(), nullable=False),
        )
        op.create_index(
            "ix_research_contradictions_lead_claim",
            "research_contradictions",
            ["lead_id", "claim_type"],
        )
        op.create_index(
            "ix_research_contradictions_workspace_id",
            "research_contradictions",
            ["workspace_id"],
        )
        op.create_index(
            "ix_research_contradictions_lead_id",
            "research_contradictions",
            ["lead_id"],
        )


def downgrade() -> None:
    bind = None if context.is_offline_mode() else op.get_bind()
    if bind is not None and _has_table(bind, "research_contradictions"):
        op.drop_table("research_contradictions")
    if bind is not None and _has_column(bind, "provider_normalized_facts", "actor_run_id"):
        op.drop_column("provider_normalized_facts", "actor_run_id")
    if bind is not None and _has_column(bind, "provider_normalized_facts", "freshness_score"):
        op.drop_column("provider_normalized_facts", "freshness_score")
