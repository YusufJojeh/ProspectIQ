"""Repair invalid scoring weight totals.

Revision ID: 0019_repair_scoring_weight_totals
Revises: 0018_web_search_confidence_weight
Create Date: 2026-07-07
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from alembic import context, op

revision = "0019_repair_scoring_weight_totals"
down_revision = "0018_web_search_confidence_weight"
branch_labels = None
depends_on = None

CANONICAL_WEIGHTS: dict[str, float] = {
    "local_trust": 0.18,
    "website_presence": 0.18,
    "search_visibility": 0.14,
    "opportunity": 0.14,
    "data_confidence": 0.08,
    "review_score": 0.13,
    "news_presence": 0.05,
    "web_search_confidence": 0.10,
}
EXPECTED_WEIGHT_TOTAL = Decimal("1.00")


def _coerce_weights(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        return json.loads(value)
    return None


def _weight_total(weights: dict[str, Any]) -> Decimal:
    return sum((Decimal(str(value)) for value in weights.values()), Decimal("0"))


def _is_valid_weight_set(weights: dict[str, Any]) -> bool:
    if set(weights) != set(CANONICAL_WEIGHTS):
        return False
    return _weight_total(weights) == EXPECTED_WEIGHT_TOTAL


def _repair_weights(weights: dict[str, Any]) -> dict[str, float]:
    if _is_valid_weight_set(weights):
        return {key: float(weights[key]) for key in CANONICAL_WEIGHTS}
    return dict(CANONICAL_WEIGHTS)


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

        repaired = _repair_weights(weights)
        if repaired != weights:
            bind.execute(
                table.update().where(table.c.id == row["id"]).values(weights_json=repaired)
            )


def downgrade() -> None:
    pass
