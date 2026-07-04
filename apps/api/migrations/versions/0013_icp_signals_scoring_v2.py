"""Add ICP profiles, lead signals, and scoring 2.0 columns.

Revision ID: 0013_icp_signals_scoring_v2
Revises: 0012_legacy_scoring_weights
Create Date: 2026-06-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op

revision = "0013_icp_signals_scoring_v2"
down_revision = "0012_legacy_scoring_weights"
branch_labels = None
depends_on = None

_LEAD_SCORE_COLUMNS: tuple[tuple[str, sa.types.TypeEngine[object]], ...] = (
    ("fit_score", sa.Float()),
    ("need_score", sa.Float()),
    ("urgency_score", sa.Float()),
    ("reachability_score", sa.Float()),
    ("final_priority_score", sa.Float()),
)


def _has_table(bind: sa.engine.Connection, table_name: str) -> bool:
    return table_name in sa.inspect(bind).get_table_names()


def _has_column(bind: sa.engine.Connection, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = None if context.is_offline_mode() else op.get_bind()

    if bind is None or not _has_table(bind, "icp_profiles"):
        op.create_table(
            "icp_profiles",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("public_id", sa.String(length=24), nullable=False),
            sa.Column("workspace_id", sa.Integer(), nullable=False),
            sa.Column("created_by_user_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("target_industries", sa.JSON(), nullable=False),
            sa.Column("target_cities", sa.JSON(), nullable=False),
            sa.Column("min_rating", sa.Float(), nullable=True),
            sa.Column("max_rating", sa.Float(), nullable=True),
            sa.Column("min_reviews", sa.Integer(), nullable=True),
            sa.Column("max_reviews", sa.Integer(), nullable=True),
            sa.Column("website_preference", sa.String(length=32), nullable=False),
            sa.Column("required_signals", sa.JSON(), nullable=False),
            sa.Column("excluded_keywords", sa.JSON(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("public_id"),
        )
        op.create_index(
            "ix_icp_profiles_workspace_active",
            "icp_profiles",
            ["workspace_id", "is_active"],
        )
        op.create_index(
            "ix_icp_profiles_workspace_name",
            "icp_profiles",
            ["workspace_id", "name"],
        )
        op.create_index(op.f("ix_icp_profiles_workspace_id"), "icp_profiles", ["workspace_id"])
        op.create_index(
            op.f("ix_icp_profiles_created_by_user_id"),
            "icp_profiles",
            ["created_by_user_id"],
        )

    if bind is None or not _has_table(bind, "lead_icp_matches"):
        op.create_table(
            "lead_icp_matches",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("public_id", sa.String(length=24), nullable=False),
            sa.Column("workspace_id", sa.Integer(), nullable=False),
            sa.Column("lead_id", sa.Integer(), nullable=False),
            sa.Column("icp_profile_id", sa.Integer(), nullable=False),
            sa.Column("fit_score", sa.Float(), nullable=False),
            sa.Column("matched", sa.Boolean(), nullable=False),
            sa.Column("match_reasons_json", sa.JSON(), nullable=False),
            sa.Column("calculated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["icp_profile_id"], ["icp_profiles.id"]),
            sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
            sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("public_id"),
        )
        op.create_index(
            "ix_lead_icp_matches_workspace_lead",
            "lead_icp_matches",
            ["workspace_id", "lead_id"],
        )
        op.create_index(
            "ix_lead_icp_matches_workspace_profile",
            "lead_icp_matches",
            ["workspace_id", "icp_profile_id"],
        )
        op.create_index(
            "ix_lead_icp_matches_lead_profile",
            "lead_icp_matches",
            ["lead_id", "icp_profile_id"],
            unique=True,
        )

    if bind is None or not _has_table(bind, "lead_signals"):
        op.create_table(
            "lead_signals",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("public_id", sa.String(length=24), nullable=False),
            sa.Column("workspace_id", sa.Integer(), nullable=False),
            sa.Column("lead_id", sa.Integer(), nullable=False),
            sa.Column("signal_type", sa.String(length=64), nullable=False),
            sa.Column("signal_strength", sa.Float(), nullable=False),
            sa.Column("evidence_text", sa.Text(), nullable=False),
            sa.Column("source_url", sa.String(length=512), nullable=True),
            sa.Column("detected_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
            sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("public_id"),
        )
        op.create_index(
            "ix_lead_signals_workspace_lead_detected",
            "lead_signals",
            ["workspace_id", "lead_id", "detected_at"],
        )
        op.create_index(
            "ix_lead_signals_workspace_type",
            "lead_signals",
            ["workspace_id", "signal_type"],
        )

    if bind is None or not _has_table(bind, "lead_signal_scores"):
        op.create_table(
            "lead_signal_scores",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("workspace_id", sa.Integer(), nullable=False),
            sa.Column("lead_id", sa.Integer(), nullable=False),
            sa.Column("signal_type", sa.String(length=64), nullable=False),
            sa.Column("score", sa.Float(), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=False),
            sa.Column("evidence_count", sa.Integer(), nullable=False),
            sa.Column("calculated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
            sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "workspace_id",
                "lead_id",
                "signal_type",
                name="uq_lead_signal_scores_workspace_lead_type",
            ),
        )
        op.create_index(
            "ix_lead_signal_scores_workspace_lead",
            "lead_signal_scores",
            ["workspace_id", "lead_id"],
        )

    for name, column_type in _LEAD_SCORE_COLUMNS:
        if bind is None or not _has_column(bind, "lead_scores", name):
            op.add_column("lead_scores", sa.Column(name, column_type, nullable=True))


def downgrade() -> None:
    for name, _ in reversed(_LEAD_SCORE_COLUMNS):
        op.drop_column("lead_scores", name)
    op.drop_table("lead_signal_scores")
    op.drop_table("lead_signals")
    op.drop_table("lead_icp_matches")
    op.drop_table("icp_profiles")
