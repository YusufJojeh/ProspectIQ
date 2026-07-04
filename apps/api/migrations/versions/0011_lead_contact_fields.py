"""Add B2B contact/enrichment columns to leads.

Revision ID: 0011_lead_contact_fields
Revises: 0010_lead_enrichments
Create Date: 2026-05-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op

revision = "0011_lead_contact_fields"
down_revision = "0010_lead_enrichments"
branch_labels = None
depends_on = None

_NEW_COLUMNS: tuple[tuple[str, sa.types.TypeEngine[object]], ...] = (
    ("email", sa.String(length=320)),
    ("email_confidence", sa.Float()),
    ("linkedin_url", sa.String(length=512)),
    ("industry", sa.String(length=255)),
    ("employee_count", sa.Integer()),
    ("ai_opener", sa.Text()),
    ("logo_url", sa.String(length=512)),
)


def _has_column(bind: sa.engine.Connection, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = None if context.is_offline_mode() else op.get_bind()
    for name, column_type in _NEW_COLUMNS:
        if bind is None or not _has_column(bind, "leads", name):
            op.add_column("leads", sa.Column(name, column_type, nullable=True))


def downgrade() -> None:
    for name, _ in reversed(_NEW_COLUMNS):
        op.drop_column("leads", name)
