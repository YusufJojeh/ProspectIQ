"""Add workspace_service_catalog_items table and outreach language column.

Revision ID: 0007_service_catalog
Revises: 0006_chat_sessions
Create Date: 2026-05-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_service_catalog"
down_revision = "0006_chat_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspace_service_catalog_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("public_id", sa.String(24), nullable=False, unique=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("service_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("rank_order", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint(
        "uq_wsc_workspace_service",
        "workspace_service_catalog_items",
        ["workspace_id", "service_name"],
    )
    op.create_index(
        "ix_wsc_workspace_rank",
        "workspace_service_catalog_items",
        ["workspace_id", "rank_order"],
    )

    op.add_column(
        "outreach_messages",
        sa.Column("language", sa.String(8), nullable=False, server_default="en"),
    )


def downgrade() -> None:
    op.drop_column("outreach_messages", "language")
    op.drop_index("ix_wsc_workspace_rank", table_name="workspace_service_catalog_items")
    op.drop_constraint(
        "uq_wsc_workspace_service", "workspace_service_catalog_items", type_="unique"
    )
    op.drop_table("workspace_service_catalog_items")
