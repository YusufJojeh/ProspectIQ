"""Initial SerpAPI-centered schema.

Revision ID: 0001_initial
Revises: 
Create Date: 2026-04-02
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("public_id", sa.String(length=24), nullable=False, unique=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("public_id", sa.String(length=24), nullable=False, unique=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("workspace_id", "email", name="uq_users_workspace_email"),
        sa.Index("ix_users_email", "email"),
    )

    op.create_table(
        "provider_settings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False, unique=True),
        sa.Column("hl", sa.String(length=16), nullable=False),
        sa.Column("gl", sa.String(length=16), nullable=False),
        sa.Column("google_domain", sa.String(length=64), nullable=False),
        sa.Column("enrich_top_n", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "search_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("public_id", sa.String(length=24), nullable=False, unique=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("requested_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("business_type", sa.String(length=255), nullable=False),
        sa.Column("city", sa.String(length=255), nullable=False),
        sa.Column("region", sa.String(length=255), nullable=True),
        sa.Column("max_results", sa.Integer(), nullable=False),
        sa.Column("min_rating", sa.Float(), nullable=True),
        sa.Column("min_reviews", sa.Integer(), nullable=True),
        sa.Column("require_website", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("queued_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("candidates_found", sa.Integer(), nullable=False),
        sa.Column("leads_upserted", sa.Integer(), nullable=False),
        sa.Column("enriched_count", sa.Integer(), nullable=False),
        sa.Column("provider_error_count", sa.Integer(), nullable=False),
    )

    op.create_table(
        "leads",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("public_id", sa.String(length=24), nullable=False, unique=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("search_job_id", sa.Integer(), sa.ForeignKey("search_jobs.id"), nullable=True, index=True),
        sa.Column("assigned_to_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True, index=True),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=255), nullable=True),
        sa.Column("address", sa.String(length=512), nullable=True),
        sa.Column("city", sa.String(length=128), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("website_url", sa.String(length=512), nullable=True),
        sa.Column("website_domain", sa.String(length=255), nullable=True, index=True),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("review_count", sa.Integer(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lng", sa.Float(), nullable=True),
        sa.Column("data_completeness", sa.Float(), nullable=False),
        sa.Column("data_confidence", sa.Float(), nullable=False),
        sa.Column("has_website", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "provider_fetches",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("public_id", sa.String(length=24), nullable=False, unique=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("engine", sa.String(length=32), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("search_job_id", sa.Integer(), sa.ForeignKey("search_jobs.id"), nullable=True, index=True),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False, index=True),
        sa.Column("request_params_json", sa.JSON(), nullable=False),
        sa.Column("serpapi_search_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Index("ix_provider_fetches_workspace_engine_mode", "workspace_id", "engine", "mode"),
    )

    op.create_table(
        "provider_raw_payloads",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider_fetch_id", sa.Integer(), sa.ForeignKey("provider_fetches.id"), nullable=False, index=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False, index=True),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "provider_normalized_facts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id"), nullable=False, index=True),
        sa.Column("provider_fetch_id", sa.Integer(), sa.ForeignKey("provider_fetches.id"), nullable=False, index=True),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("data_cid", sa.String(length=128), nullable=True, index=True),
        sa.Column("data_id", sa.String(length=128), nullable=True, index=True),
        sa.Column("place_id", sa.String(length=128), nullable=True, index=True),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=255), nullable=True),
        sa.Column("address", sa.String(length=512), nullable=True),
        sa.Column("city", sa.String(length=128), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("website_url", sa.String(length=512), nullable=True),
        sa.Column("website_domain", sa.String(length=255), nullable=True, index=True),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("review_count", sa.Integer(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lng", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("completeness", sa.Float(), nullable=False),
        sa.Column("facts_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "lead_source_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id"), nullable=False, index=True),
        sa.Column(
            "provider_normalized_fact_id",
            sa.Integer(),
            sa.ForeignKey("provider_normalized_facts.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "lead_identities",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id"), nullable=False, index=True),
        sa.Column("identity_type", sa.String(length=32), nullable=False),
        sa.Column("identity_value", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "workspace_id", "identity_type", "identity_value", name="uq_lead_identities_workspace_key"
        ),
        sa.Index("ix_lead_identities_lookup", "workspace_id", "identity_type", "identity_value"),
    )

    op.create_table(
        "scoring_config_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("public_id", sa.String(length=24), nullable=False, unique=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("weights_json", sa.JSON(), nullable=False),
        sa.Column("thresholds_json", sa.JSON(), nullable=False),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "workspace_scoring_active",
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), primary_key=True),
        sa.Column(
            "active_scoring_config_version_id",
            sa.Integer(),
            sa.ForeignKey("scoring_config_versions.id"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "lead_scores",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id"), nullable=False, index=True),
        sa.Column(
            "scoring_config_version_id",
            sa.Integer(),
            sa.ForeignKey("scoring_config_versions.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("total_score", sa.Float(), nullable=False),
        sa.Column("band", sa.String(length=32), nullable=False),
        sa.Column("qualified", sa.Boolean(), nullable=False),
        sa.Column("scored_at", sa.DateTime(), nullable=False),
        sa.Index("ix_lead_scores_lead_scored_at", "lead_id", "scored_at"),
    )

    op.create_table(
        "score_breakdowns",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("lead_score_id", sa.Integer(), sa.ForeignKey("lead_scores.id"), nullable=False, index=True),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("contribution", sa.Float(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Index("ix_score_breakdowns_lead_score_key", "lead_score_id", "key"),
    )

    op.create_table(
        "prompt_templates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("public_id", sa.String(length=24), nullable=False, unique=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("template_text", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "ai_analysis_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("public_id", sa.String(length=24), nullable=False, unique=True),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id"), nullable=False, index=True),
        sa.Column("prompt_template_id", sa.Integer(), sa.ForeignKey("prompt_templates.id"), nullable=False, index=True),
        sa.Column("ai_provider", sa.String(length=32), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False, index=True),
        sa.Column("output_json", sa.JSON(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "outreach_messages",
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
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("edited_subject", sa.String(length=255), nullable=True),
        sa.Column("edited_message", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "lead_notes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("public_id", sa.String(length=24), nullable=False, unique=True),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id"), nullable=False, index=True),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "lead_status_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id"), nullable=False, index=True),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("changed_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("changed_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("public_id", sa.String(length=24), nullable=False, unique=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True, index=True),
        sa.Column("event_name", sa.String(length=128), nullable=False),
        sa.Column("details", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Index("ix_audit_logs_workspace_created_at", "workspace_id", "created_at"),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("lead_status_history")
    op.drop_table("lead_notes")
    op.drop_table("outreach_messages")
    op.drop_table("ai_analysis_snapshots")
    op.drop_table("prompt_templates")
    op.drop_table("score_breakdowns")
    op.drop_table("lead_scores")
    op.drop_table("workspace_scoring_active")
    op.drop_table("scoring_config_versions")
    op.drop_table("lead_identities")
    op.drop_table("lead_source_records")
    op.drop_table("provider_normalized_facts")
    op.drop_table("provider_raw_payloads")
    op.drop_table("provider_fetches")
    op.drop_table("leads")
    op.drop_table("search_jobs")
    op.drop_table("provider_settings")
    op.drop_table("users")
    op.drop_table("workspaces")

