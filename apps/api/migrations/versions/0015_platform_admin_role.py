"""Seed the platform_admin role for SaaS platform administration.

Revision ID: 0015_platform_admin_role
Revises: 0014_ai_evidence_feedback
Create Date: 2026-06-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op

revision = "0015_platform_admin_role"
down_revision = "0014_ai_evidence_feedback"
branch_labels = None
depends_on = None

_ROLE_KEY = "platform_admin"


def upgrade() -> None:
    bind = None if context.is_offline_mode() else op.get_bind()

    roles = sa.table(
        "roles",
        sa.column("key", sa.String),
        sa.column("label", sa.String),
        sa.column("description", sa.Text),
    )

    if bind is not None:
        existing = bind.execute(
            sa.select(sa.func.count())
            .select_from(sa.table("roles", sa.column("key", sa.String)))
            .where(sa.column("key") == _ROLE_KEY)
        ).scalar()
        if existing:
            return

    op.bulk_insert(
        roles,
        [
            {
                "key": _ROLE_KEY,
                "label": "Platform Admin",
                "description": "Platform-level SaaS operator access.",
            }
        ],
    )


def downgrade() -> None:
    bind = None if context.is_offline_mode() else op.get_bind()
    if bind is None:
        return
    bind.execute(
        sa.text("DELETE FROM roles WHERE key = :key"),
        {"key": _ROLE_KEY},
    )
