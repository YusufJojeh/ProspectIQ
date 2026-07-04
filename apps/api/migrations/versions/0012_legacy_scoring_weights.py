"""Backfill legacy scoring weight dimensions.

Revision ID: 0012_legacy_scoring_weights
Revises: 0011_lead_contact_fields
Create Date: 2026-05-30
"""

from __future__ import annotations

import json
from typing import Any

import sqlalchemy as sa
from alembic import context, op

revision = "0012_legacy_scoring_weights"
down_revision = "0011_lead_contact_fields"
branch_labels = None
depends_on = None


def _coerce_weights(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        return json.loads(value)
    return None


def upgrade() -> None:
    if context.is_offline_mode():
        return

    bind = op.get_bind()
    table = sa.table(
        "scoring_config_versions",
        sa.column("id", sa.Integer()),
        sa.column("weights_json", sa.JSON()),
    )

    rows = bind.execute(sa.select(table.c.id, table.c.weights_json)).mappings()
    for row in rows:
        weights = _coerce_weights(row["weights_json"])
        if weights is None:
            continue

        changed = False
        for key in ("review_score", "news_presence"):
            if key not in weights:
                weights[key] = 0.0
                changed = True

        if changed:
            bind.execute(
                table.update()
                .where(table.c.id == row["id"])
                .values(weights_json=weights)
            )


def downgrade() -> None:
    pass
