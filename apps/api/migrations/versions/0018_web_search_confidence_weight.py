"""Backfill web_search_confidence scoring weight dimension.

Revision ID: 0018_web_search_confidence_weight
Revises: 0017_crm_pipeline
Create Date: 2026-07-04
"""

from __future__ import annotations

import json
from typing import Any

import sqlalchemy as sa
from alembic import context, op

revision = "0018_web_search_confidence_weight"
down_revision = "0017_crm_pipeline"
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
        if weights is None or "web_search_confidence" in weights:
            continue

        # Backfill as 0.0 so previously persisted weight totals (which already
        # sum to 1.0 without this new Tavily-evidence dimension) stay valid.
        # New/updated scoring configs use ScoringWeights' rebalanced defaults.
        weights["web_search_confidence"] = 0.0
        bind.execute(
            table.update().where(table.c.id == row["id"]).values(weights_json=weights)
        )


def downgrade() -> None:
    pass
