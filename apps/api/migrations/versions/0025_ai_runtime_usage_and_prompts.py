"""AI runtime usage ledger and versioned prompt registry.

Adds the single provider usage ledger that every AI caller writes to, and
the versioned prompt registry an AgentRun points at. Both are additive; no
existing table is altered.

Revision ID: 0025_ai_runtime_usage_and_prompts
Revises: 0024_sales_knowledge_rag
Create Date: 2026-09-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0025_ai_runtime_usage_and_prompts"
down_revision = "0024_sales_knowledge_rag"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("provider_usage"):
        op.create_table(
            "provider_usage",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("public_id", sa.String(length=24), nullable=False),
            sa.Column("workspace_id", sa.Integer(), nullable=False),
            sa.Column("trace_id", sa.String(length=64), nullable=False),
            sa.Column("operation", sa.String(length=32), nullable=False),
            sa.Column("subject_id", sa.String(length=64), nullable=True),
            sa.Column("provider", sa.String(length=32), nullable=False),
            sa.Column("model", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("embedding_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("units", sa.Integer(), nullable=False, server_default="0"),
            # Nullable on purpose: NULL is "no configured rate", which must
            # stay distinguishable from a genuinely free call.
            sa.Column("cost_micro_usd", sa.Integer(), nullable=True),
            sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="ok"),
            sa.Column("fallback_from", sa.String(length=64), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("public_id"),
        )
        op.create_index(
            "ix_provider_usage_workspace_created",
            "provider_usage",
            ["workspace_id", "created_at"],
        )
        op.create_index("ix_provider_usage_trace", "provider_usage", ["trace_id"])
        op.create_index(
            "ix_provider_usage_operation", "provider_usage", ["operation"]
        )
        op.create_index("ix_provider_usage_subject", "provider_usage", ["subject_id"])
        op.create_index("ix_provider_usage_provider", "provider_usage", ["provider"])
        op.create_index("ix_provider_usage_status", "provider_usage", ["status"])
        op.create_index(
            "ix_provider_usage_workspace_id", "provider_usage", ["workspace_id"]
        )

    if not inspector.has_table("prompt_versions"):
        op.create_table(
            "prompt_versions",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("public_id", sa.String(length=24), nullable=False),
            sa.Column("prompt_key", sa.String(length=64), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("checksum", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("activated_at", sa.DateTime(), nullable=True),
            sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("public_id"),
        )
        op.create_index(
            "ix_prompt_versions_key_version",
            "prompt_versions",
            ["prompt_key", "version"],
            unique=True,
        )
        op.create_index("ix_prompt_versions_status", "prompt_versions", ["status"])
        op.create_index("ix_prompt_versions_key", "prompt_versions", ["prompt_key"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("prompt_versions"):
        op.drop_table("prompt_versions")
    if inspector.has_table("provider_usage"):
        op.drop_table("provider_usage")
