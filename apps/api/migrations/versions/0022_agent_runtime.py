"""Add agent_runs, agent_messages, agent_tool_calls, agent_actions, and
agent_events tables for the general-purpose Operational Agent Runtime.

Revision ID: 0022_agent_runtime
Revises: 0021_research_delta_intelligence
Create Date: 2026-09-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op

revision = "0022_agent_runtime"
down_revision = "0021_research_delta_intelligence"
branch_labels = None
depends_on = None


def _has_table(bind: sa.engine.Connection, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def upgrade() -> None:
    bind = None if context.is_offline_mode() else op.get_bind()
    if bind is None:
        return

    if not _has_table(bind, "agent_runs"):
        op.create_table(
            "agent_runs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("public_id", sa.String(length=24), nullable=False, unique=True),
            sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
            sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id"), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("goal", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
            sa.Column("provider", sa.String(length=32), nullable=False, server_default="openai"),
            sa.Column("model", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("step_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("tool_call_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("external_search_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("crawl_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("write_proposal_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("fallback_used", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("latency_ms", sa.Integer(), nullable=True),
            sa.Column("trace_id", sa.String(length=64), nullable=False),
            sa.Column("final_answer_json", sa.JSON(), nullable=True),
            sa.Column("error_code", sa.String(length=64), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_agent_runs_workspace_id", "agent_runs", ["workspace_id"])
        op.create_index("ix_agent_runs_lead_id", "agent_runs", ["lead_id"])
        op.create_index("ix_agent_runs_created_by_user_id", "agent_runs", ["created_by_user_id"])
        op.create_index("ix_agent_runs_status", "agent_runs", ["status"])
        op.create_index(
            "ix_agent_runs_workspace_created_at", "agent_runs", ["workspace_id", "created_at"]
        )

    if not _has_table(bind, "agent_messages"):
        op.create_table(
            "agent_messages",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("agent_run_id", sa.Integer(), sa.ForeignKey("agent_runs.id"), nullable=False),
            sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
            sa.Column("seq", sa.Integer(), nullable=False),
            sa.Column("role", sa.String(length=16), nullable=False),
            sa.Column("content", sa.Text(), nullable=True),
            sa.Column("tool_name", sa.String(length=64), nullable=True),
            sa.Column("tool_call_public_id", sa.String(length=24), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_agent_messages_agent_run_id", "agent_messages", ["agent_run_id"])
        op.create_index("ix_agent_messages_workspace_id", "agent_messages", ["workspace_id"])
        op.create_index("ix_agent_messages_run_seq", "agent_messages", ["agent_run_id", "seq"])

    if not _has_table(bind, "agent_tool_calls"):
        op.create_table(
            "agent_tool_calls",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("public_id", sa.String(length=24), nullable=False, unique=True),
            sa.Column("agent_run_id", sa.Integer(), sa.ForeignKey("agent_runs.id"), nullable=False),
            sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
            sa.Column("seq", sa.Integer(), nullable=False),
            sa.Column("tool_name", sa.String(length=64), nullable=False),
            sa.Column("tool_type", sa.String(length=24), nullable=False),
            sa.Column("arguments_json", sa.JSON(), nullable=False),
            sa.Column("arguments_hash", sa.String(length=64), nullable=False),
            sa.Column("result_json", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(length=24), nullable=False, server_default="pending"),
            sa.Column("duration_ms", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_agent_tool_calls_agent_run_id", "agent_tool_calls", ["agent_run_id"])
        op.create_index("ix_agent_tool_calls_workspace_id", "agent_tool_calls", ["workspace_id"])
        op.create_index("ix_agent_tool_calls_run_seq", "agent_tool_calls", ["agent_run_id", "seq"])
        op.create_index(
            "ix_agent_tool_calls_run_hash", "agent_tool_calls", ["agent_run_id", "arguments_hash"]
        )
        op.create_index("ix_agent_tool_calls_arguments_hash", "agent_tool_calls", ["arguments_hash"])

    if not _has_table(bind, "agent_actions"):
        op.create_table(
            "agent_actions",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("public_id", sa.String(length=24), nullable=False, unique=True),
            sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
            sa.Column("agent_run_id", sa.Integer(), sa.ForeignKey("agent_runs.id"), nullable=False),
            sa.Column(
                "tool_call_id", sa.Integer(), sa.ForeignKey("agent_tool_calls.id"), nullable=True
            ),
            sa.Column("tool_name", sa.String(length=64), nullable=False),
            sa.Column("resource_type", sa.String(length=32), nullable=False),
            sa.Column("resource_id", sa.String(length=64), nullable=False),
            sa.Column("payload_json", sa.JSON(), nullable=False),
            sa.Column("payload_hash", sa.String(length=64), nullable=False),
            sa.Column("preview_json", sa.JSON(), nullable=False),
            sa.Column("risk_level", sa.String(length=16), nullable=False),
            sa.Column("status", sa.String(length=24), nullable=False, server_default="pending"),
            sa.Column("result_json", sa.JSON(), nullable=True),
            sa.Column(
                "approved_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True
            ),
            sa.Column("approved_at", sa.DateTime(), nullable=True),
            sa.Column("executed_at", sa.DateTime(), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("failure_code", sa.String(length=64), nullable=True),
            sa.Column("failure_message", sa.Text(), nullable=True),
            sa.Column("idempotency_key", sa.String(length=64), nullable=False, unique=True),
            sa.Column("trace_id", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_agent_actions_workspace_id", "agent_actions", ["workspace_id"])
        op.create_index("ix_agent_actions_agent_run_id", "agent_actions", ["agent_run_id"])
        op.create_index("ix_agent_actions_status", "agent_actions", ["status"])
        op.create_index(
            "ix_agent_actions_workspace_status", "agent_actions", ["workspace_id", "status"]
        )
        op.create_index("ix_agent_actions_run_id", "agent_actions", ["agent_run_id"])

    if not _has_table(bind, "agent_events"):
        op.create_table(
            "agent_events",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("public_id", sa.String(length=24), nullable=False, unique=True),
            sa.Column("agent_run_id", sa.Integer(), sa.ForeignKey("agent_runs.id"), nullable=False),
            sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
            sa.Column("seq", sa.Integer(), nullable=False),
            sa.Column("event_type", sa.String(length=32), nullable=False),
            sa.Column("payload_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_agent_events_agent_run_id", "agent_events", ["agent_run_id"])
        op.create_index("ix_agent_events_workspace_id", "agent_events", ["workspace_id"])
        op.create_index("ix_agent_events_run_seq", "agent_events", ["agent_run_id", "seq"])


def downgrade() -> None:
    bind = None if context.is_offline_mode() else op.get_bind()
    if bind is None:
        return
    if _has_table(bind, "agent_events"):
        op.drop_table("agent_events")
    if _has_table(bind, "agent_actions"):
        op.drop_table("agent_actions")
    if _has_table(bind, "agent_tool_calls"):
        op.drop_table("agent_tool_calls")
    if _has_table(bind, "agent_messages"):
        op.drop_table("agent_messages")
    if _has_table(bind, "agent_runs"):
        op.drop_table("agent_runs")
