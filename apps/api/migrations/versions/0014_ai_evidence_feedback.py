"""Add AI analysis evidence and feedback tables.

Revision ID: 0014_ai_evidence_feedback
Revises: 0013_icp_signals_scoring_v2
Create Date: 2026-06-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op

revision = "0014_ai_evidence_feedback"
down_revision = "0013_icp_signals_scoring_v2"
branch_labels = None
depends_on = None


def _has_table(bind: sa.engine.Connection, table_name: str) -> bool:
    return table_name in sa.inspect(bind).get_table_names()


def upgrade() -> None:
    bind = None if context.is_offline_mode() else op.get_bind()

    if bind is None or not _has_table(bind, "ai_analysis_evidence"):
        op.create_table(
            "ai_analysis_evidence",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("public_id", sa.String(length=24), nullable=False),
            sa.Column("workspace_id", sa.Integer(), nullable=False),
            sa.Column("ai_analysis_snapshot_id", sa.Integer(), nullable=False),
            sa.Column("source_type", sa.String(length=64), nullable=False),
            sa.Column("source_url", sa.String(length=512), nullable=True),
            sa.Column("evidence_text", sa.Text(), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["ai_analysis_snapshot_id"], ["ai_analysis_snapshots.id"]),
            sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("public_id"),
        )
        op.create_index(
            op.f("ix_ai_analysis_evidence_workspace_id"),
            "ai_analysis_evidence",
            ["workspace_id"],
        )
        op.create_index(
            op.f("ix_ai_analysis_evidence_ai_analysis_snapshot_id"),
            "ai_analysis_evidence",
            ["ai_analysis_snapshot_id"],
        )
        op.create_index(
            "ix_ai_analysis_evidence_snapshot",
            "ai_analysis_evidence",
            ["ai_analysis_snapshot_id"],
        )
        op.create_index(
            "ix_ai_analysis_evidence_workspace_snapshot",
            "ai_analysis_evidence",
            ["workspace_id", "ai_analysis_snapshot_id"],
        )

    if bind is None or not _has_table(bind, "ai_feedback"):
        op.create_table(
            "ai_feedback",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("public_id", sa.String(length=24), nullable=False),
            sa.Column("workspace_id", sa.Integer(), nullable=False),
            sa.Column("ai_analysis_snapshot_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("rating", sa.String(length=16), nullable=False),
            sa.Column("correction_text", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["ai_analysis_snapshot_id"], ["ai_analysis_snapshots.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("public_id"),
        )
        op.create_index(
            op.f("ix_ai_feedback_workspace_id"), "ai_feedback", ["workspace_id"]
        )
        op.create_index(
            op.f("ix_ai_feedback_ai_analysis_snapshot_id"),
            "ai_feedback",
            ["ai_analysis_snapshot_id"],
        )
        op.create_index(op.f("ix_ai_feedback_user_id"), "ai_feedback", ["user_id"])
        op.create_index("ix_ai_feedback_snapshot", "ai_feedback", ["ai_analysis_snapshot_id"])
        op.create_index("ix_ai_feedback_user", "ai_feedback", ["user_id"])
        op.create_index(
            "ix_ai_feedback_workspace_snapshot",
            "ai_feedback",
            ["workspace_id", "ai_analysis_snapshot_id"],
        )


def downgrade() -> None:
    op.drop_table("ai_feedback")
    op.drop_table("ai_analysis_evidence")
