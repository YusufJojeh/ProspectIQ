"""Add chat_sessions and chat_messages tables for assistant persistence.

Revision ID: 0006_chat_sessions
Revises: 0005_auth_billing_workspace_refactor
Create Date: 2026-05-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_chat_sessions"
down_revision = "0005_auth_billing_workspace_refactor"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("public_id", sa.String(24), nullable=False, unique=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "lead_id",
            sa.Integer(),
            sa.ForeignKey("leads.id"),
            nullable=True,
            index=True,
        ),
        sa.Column("title", sa.String(255), nullable=False, server_default="New Chat"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_chat_sessions_workspace_created_at",
        "chat_sessions",
        ["workspace_id", "created_at"],
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("public_id", sa.String(24), nullable=False, unique=True),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("chat_sessions.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_chat_messages_session_created_at",
        "chat_messages",
        ["session_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_chat_messages_session_created_at", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_sessions_workspace_created_at", table_name="chat_sessions")
    op.drop_table("chat_sessions")
