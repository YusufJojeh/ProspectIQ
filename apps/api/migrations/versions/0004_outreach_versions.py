"""Add outreach tone and versioning columns.

Revision ID: 0004_outreach_versions
Revises: 0003_roles_and_search_filters
Create Date: 2026-04-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_outreach_versions"
down_revision = "0003_roles_and_search_filters"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "outreach_messages",
        sa.Column(
            "tone",
            sa.String(length=32),
            nullable=False,
            server_default="consultative",
        ),
    )
    op.add_column(
        "outreach_messages",
        sa.Column(
            "version_number",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )
    op.create_index(
        "ix_outreach_messages_lead_version",
        "outreach_messages",
        ["lead_id", "version_number"],
    )


def downgrade() -> None:
    op.drop_index("ix_outreach_messages_lead_version", table_name="outreach_messages")
    op.drop_column("outreach_messages", "version_number")
    op.drop_column("outreach_messages", "tone")
