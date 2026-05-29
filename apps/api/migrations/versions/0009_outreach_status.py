"""Add outreach_status column to outreach_messages.

Revision ID: 0009_outreach_status
Revises: 0008_db_hardening_integrity
Create Date: 2026-05-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op

revision = "0009_outreach_status"
down_revision = "0008_db_hardening_integrity"
branch_labels = None
depends_on = None


def _has_column(bind: sa.engine.Connection, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = None if context.is_offline_mode() else op.get_bind()
    if bind is None or not _has_column(bind, "outreach_messages", "outreach_status"):
        op.add_column(
            "outreach_messages",
            sa.Column("outreach_status", sa.String(16), nullable=False, server_default="draft"),
        )


def downgrade() -> None:
    op.drop_column("outreach_messages", "outreach_status")
