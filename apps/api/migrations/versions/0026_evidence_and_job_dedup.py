"""Evidence fact and search job de-duplication keys.

Adds provider_normalized_facts.source_unique_id (stable per-source identity used
to upsert repeated provider evidence) and search_jobs.dedup_fingerprint (used to
return an already-active job for an identical request). Both are additive and
nullable/defaulted; existing rows keep "" / NULL and are treated as un-keyed.

Revision ID: 0026_evidence_and_job_dedup
Revises: 0025_ai_runtime_usage_and_prompts
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0026_evidence_and_job_dedup"
down_revision = "0025_ai_runtime_usage_and_prompts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "provider_normalized_facts",
        sa.Column("source_unique_id", sa.String(length=128), nullable=False, server_default=""),
    )
    op.create_index(
        "ix_provider_norm_fact_dedup",
        "provider_normalized_facts",
        ["workspace_id", "lead_id", "source_type", "source_unique_id"],
    )
    op.add_column(
        "search_jobs",
        sa.Column("dedup_fingerprint", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_search_jobs_dedup_fingerprint", "search_jobs", ["dedup_fingerprint"])


def downgrade() -> None:
    op.drop_index("ix_search_jobs_dedup_fingerprint", table_name="search_jobs")
    op.drop_column("search_jobs", "dedup_fingerprint")
    op.drop_index("ix_provider_norm_fact_dedup", table_name="provider_normalized_facts")
    op.drop_column("provider_normalized_facts", "source_unique_id")
