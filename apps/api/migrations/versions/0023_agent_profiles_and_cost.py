"""Add agent profile, prompt version, stop reason and cost/usage counters to
agent_runs.

These columns make a completed run fully reconstructable: which profile's
policy governed it, which prompt version it ran under, why it stopped, and
what it cost. Every column is additive and nullable-or-defaulted, so an
existing row keeps its meaning without backfill.

Revision ID: 0023_agent_profiles_and_cost
Revises: 0022_agent_runtime
Create Date: 2026-09-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op

revision = "0023_agent_profiles_and_cost"
down_revision = "0022_agent_runtime"
branch_labels = None
depends_on = None

_NEW_COLUMNS: tuple[tuple[str, sa.Column], ...] = (
    ("profile", sa.Column("profile", sa.String(length=32), nullable=False, server_default="research")),
    ("prompt_key", sa.Column("prompt_key", sa.String(length=64), nullable=True)),
    ("prompt_version", sa.Column("prompt_version", sa.Integer(), nullable=True)),
    ("stop_reason", sa.Column("stop_reason", sa.String(length=64), nullable=True)),
    ("rag_query_count", sa.Column("rag_query_count", sa.Integer(), nullable=False, server_default="0")),
    ("model_call_count", sa.Column("model_call_count", sa.Integer(), nullable=False, server_default="0")),
    ("embedding_tokens", sa.Column("embedding_tokens", sa.Integer(), nullable=False, server_default="0")),
    ("cost_micro_usd", sa.Column("cost_micro_usd", sa.Integer(), nullable=False, server_default="0")),
)


def _existing_columns(bind: sa.engine.Connection, table_name: str) -> set[str]:
    inspector = sa.inspect(bind)
    if not inspector.has_table(table_name):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = None if context.is_offline_mode() else op.get_bind()
    if bind is None:
        return

    existing = _existing_columns(bind, "agent_runs")
    if not existing:
        return
    for name, column in _NEW_COLUMNS:
        if name not in existing:
            op.add_column("agent_runs", column)

    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("agent_runs")}
    if "ix_agent_runs_profile" not in indexes and "profile" not in existing:
        op.create_index("ix_agent_runs_profile", "agent_runs", ["profile"])


def downgrade() -> None:
    bind = None if context.is_offline_mode() else op.get_bind()
    if bind is None:
        return

    existing = _existing_columns(bind, "agent_runs")
    if not existing:
        return

    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("agent_runs")}
    if "ix_agent_runs_profile" in indexes:
        op.drop_index("ix_agent_runs_profile", table_name="agent_runs")
    for name, _column in reversed(_NEW_COLUMNS):
        if name in existing:
            op.drop_column("agent_runs", name)
