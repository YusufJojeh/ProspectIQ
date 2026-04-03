"""Add roles, search requests, service recommendations, and system settings.

Revision ID: 0002_schema_extensions
Revises: 0001_initial
Create Date: 2026-04-03
"""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import context, op

from app.shared.utils.identifiers import new_public_id

revision = "0002_schema_extensions"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


roles_table = sa.table(
    "roles",
    sa.column("key", sa.String(length=32)),
    sa.column("label", sa.String(length=64)),
    sa.column("description", sa.Text()),
    sa.column("created_at", sa.DateTime()),
)


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(length=32), nullable=False, unique=True),
        sa.Column("label", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.bulk_insert(
        roles_table,
        [
            {
                "key": "admin",
                "label": "Administrator",
                "description": "Full workspace administration.",
                "created_at": datetime.now(tz=UTC),
            },
            {
                "key": "manager",
                "label": "Manager",
                "description": "Operational lead and scoring oversight.",
                "created_at": datetime.now(tz=UTC),
            },
            {
                "key": "sales",
                "label": "Sales",
                "description": "Lead qualification and outreach execution.",
                "created_at": datetime.now(tz=UTC),
            },
        ],
    )
    op.create_foreign_key("fk_users_role_key", "users", "roles", ["role"], ["key"])

    op.create_table(
        "search_requests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("public_id", sa.String(length=24), nullable=False, unique=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "requested_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("business_type", sa.String(length=255), nullable=False),
        sa.Column("city", sa.String(length=255), nullable=False),
        sa.Column("region", sa.String(length=255), nullable=True),
        sa.Column("max_results", sa.Integer(), nullable=False),
        sa.Column("min_rating", sa.Float(), nullable=True),
        sa.Column("min_reviews", sa.Integer(), nullable=True),
        sa.Column("require_website", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Index("ix_search_requests_workspace_created_at", "workspace_id", "created_at"),
    )
    op.add_column("search_jobs", sa.Column("search_request_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_search_jobs_search_request_id",
        "search_jobs",
        "search_requests",
        ["search_request_id"],
        ["id"],
    )
    op.create_index("ix_search_jobs_search_request_id", "search_jobs", ["search_request_id"])
    op.create_index(
        "ix_search_jobs_workspace_status_queued_at",
        "search_jobs",
        ["workspace_id", "status", "queued_at"],
    )

    bind = None
    if not context.is_offline_mode():
        bind = op.get_bind()
        search_jobs = list(
            bind.execute(
                sa.text(
                    """
                    SELECT
                        id,
                        workspace_id,
                        requested_by_user_id,
                        business_type,
                        city,
                        region,
                        max_results,
                        min_rating,
                        min_reviews,
                        require_website,
                        queued_at
                    FROM search_jobs
                    """
                )
            ).mappings()
        )
        for row in search_jobs:
            search_request_result = bind.execute(
                sa.text(
                    """
                    INSERT INTO search_requests (
                        public_id,
                        workspace_id,
                        requested_by_user_id,
                        business_type,
                        city,
                        region,
                        max_results,
                        min_rating,
                        min_reviews,
                        require_website,
                        created_at
                    ) VALUES (
                        :public_id,
                        :workspace_id,
                        :requested_by_user_id,
                        :business_type,
                        :city,
                        :region,
                        :max_results,
                        :min_rating,
                        :min_reviews,
                        :require_website,
                        :created_at
                    )
                    """
                ),
                {
                    "public_id": new_public_id("srq"),
                    "workspace_id": row["workspace_id"],
                    "requested_by_user_id": row["requested_by_user_id"],
                    "business_type": row["business_type"],
                    "city": row["city"],
                    "region": row["region"],
                    "max_results": row["max_results"],
                    "min_rating": row["min_rating"],
                    "min_reviews": row["min_reviews"],
                    "require_website": row["require_website"],
                    "created_at": row["queued_at"],
                },
            )
            bind.execute(
                sa.text(
                    """
                    UPDATE search_jobs
                    SET search_request_id = :search_request_id
                    WHERE id = :job_id
                    """
                ),
                {
                    "search_request_id": search_request_result.lastrowid,
                    "job_id": row["id"],
                },
            )

    op.create_table(
        "service_recommendations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("public_id", sa.String(length=24), nullable=False, unique=True),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id"), nullable=False, index=True),
        sa.Column(
            "ai_analysis_snapshot_id",
            sa.Integer(),
            sa.ForeignKey("ai_analysis_snapshots.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("service_name", sa.String(length=255), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("rank_order", sa.Integer(), nullable=False),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "ai_analysis_snapshot_id",
            "rank_order",
            name="uq_service_recommendations_snapshot_rank",
        ),
        sa.Index("ix_service_recommendations_lead_created_at", "lead_id", "created_at"),
    )

    if bind is not None:
        snapshots = list(
            bind.execute(
                sa.text(
                    """
                    SELECT id, lead_id, output_json, created_by_user_id, created_at
                    FROM ai_analysis_snapshots
                    """
                )
            ).mappings()
        )
        for snapshot in snapshots:
            output_json = snapshot["output_json"] or {}
            services = output_json.get("recommended_services")
            if not isinstance(services, list):
                continue
            for rank_order, service_name in enumerate(services, start=1):
                if not isinstance(service_name, str) or not service_name.strip():
                    continue
                bind.execute(
                    sa.text(
                        """
                        INSERT INTO service_recommendations (
                            public_id,
                            lead_id,
                            ai_analysis_snapshot_id,
                            service_name,
                            rationale,
                            confidence,
                            rank_order,
                            created_by_user_id,
                            created_at
                        ) VALUES (
                            :public_id,
                            :lead_id,
                            :ai_analysis_snapshot_id,
                            :service_name,
                            :rationale,
                            :confidence,
                            :rank_order,
                            :created_by_user_id,
                            :created_at
                        )
                        """
                    ),
                    {
                        "public_id": new_public_id("srv"),
                        "lead_id": snapshot["lead_id"],
                        "ai_analysis_snapshot_id": snapshot["id"],
                        "service_name": service_name.strip(),
                        "rationale": None,
                        "confidence": output_json.get("confidence"),
                        "rank_order": rank_order,
                        "created_by_user_id": snapshot["created_by_user_id"],
                        "created_at": snapshot["created_at"],
                    },
                )

    op.create_table(
        "system_settings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(length=128), nullable=False, unique=True),
        sa.Column("value_json", sa.JSON(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "updated_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
            index=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_index(
        "ix_leads_workspace_status_updated_at",
        "leads",
        ["workspace_id", "status", "updated_at"],
    )
    op.create_index("ix_leads_workspace_city", "leads", ["workspace_id", "city"])
    op.create_index(
        "ix_provider_normalized_facts_lead_source_created_at",
        "provider_normalized_facts",
        ["lead_id", "source_type", "created_at"],
    )
    op.create_index(
        "ix_ai_analysis_snapshots_lead_created_at",
        "ai_analysis_snapshots",
        ["lead_id", "created_at"],
    )
    op.create_index(
        "ix_outreach_messages_lead_created_at",
        "outreach_messages",
        ["lead_id", "created_at"],
    )
    op.create_index(
        "ix_lead_status_history_lead_changed_at",
        "lead_status_history",
        ["lead_id", "changed_at"],
    )
    op.create_index("ix_lead_notes_lead_created_at", "lead_notes", ["lead_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_lead_notes_lead_created_at", table_name="lead_notes")
    op.drop_index("ix_lead_status_history_lead_changed_at", table_name="lead_status_history")
    op.drop_index("ix_outreach_messages_lead_created_at", table_name="outreach_messages")
    op.drop_index("ix_ai_analysis_snapshots_lead_created_at", table_name="ai_analysis_snapshots")
    op.drop_index(
        "ix_provider_normalized_facts_lead_source_created_at",
        table_name="provider_normalized_facts",
    )
    op.drop_index("ix_leads_workspace_city", table_name="leads")
    op.drop_index("ix_leads_workspace_status_updated_at", table_name="leads")
    op.drop_table("system_settings")
    op.drop_table("service_recommendations")
    op.drop_index("ix_search_jobs_workspace_status_queued_at", table_name="search_jobs")
    op.drop_index("ix_search_jobs_search_request_id", table_name="search_jobs")
    op.drop_constraint("fk_search_jobs_search_request_id", "search_jobs", type_="foreignkey")
    op.drop_column("search_jobs", "search_request_id")
    op.drop_table("search_requests")
    op.drop_constraint("fk_users_role_key", "users", type_="foreignkey")
    op.drop_table("roles")
