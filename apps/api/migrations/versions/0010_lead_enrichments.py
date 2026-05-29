"""Add enrichments JSON column to leads.

Revision ID: 0010_lead_enrichments
Revises: 0009_outreach_status
Create Date: 2026-05-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op

revision = "0010_lead_enrichments"
down_revision = "0009_outreach_status"
branch_labels = None
depends_on = None


def _has_column(bind: sa.engine.Connection, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = None if context.is_offline_mode() else op.get_bind()
    if bind is None or not _has_column(bind, "leads", "enrichments"):
        op.add_column("leads", sa.Column("enrichments", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("leads", "enrichments")
