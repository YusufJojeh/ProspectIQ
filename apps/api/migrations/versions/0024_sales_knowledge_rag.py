"""Create the sales knowledge store: collections, documents, versions, chunks
and ingestion runs.

Chunk embeddings are stored as JSON float arrays rather than a native vector
type because the deployment target is MariaDB/MySQL, where no vector column or
index exists. Each chunk records the model and dimension that produced its
vector so a model change can never silently mix incompatible vector spaces.

Revision ID: 0024_sales_knowledge_rag
Revises: 0023_agent_profiles_and_cost
Create Date: 2026-09-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op

revision = "0024_sales_knowledge_rag"
down_revision = "0023_agent_profiles_and_cost"
branch_labels = None
depends_on = None

_TABLES = (
    "knowledge_ingestion_runs",
    "knowledge_chunks",
    "knowledge_document_versions",
    "knowledge_documents",
    "knowledge_collections",
)


def _has_table(bind: sa.engine.Connection, name: str) -> bool:
    return sa.inspect(bind).has_table(name)


def upgrade() -> None:
    bind = None if context.is_offline_mode() else op.get_bind()
    if bind is None:
        return

    if not _has_table(bind, "knowledge_collections"):
        op.create_table(
            "knowledge_collections",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("public_id", sa.String(length=24), nullable=False),
            sa.Column("workspace_id", sa.Integer(), nullable=False),
            sa.Column("slug", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=160), nullable=False),
            sa.Column("collection_type", sa.String(length=32), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("public_id"),
            sa.UniqueConstraint(
                "workspace_id", "slug", name="uq_knowledge_collections_workspace_slug"
            ),
        )
        op.create_index(
            "ix_knowledge_collections_workspace_id", "knowledge_collections", ["workspace_id"]
        )
        op.create_index(
            "ix_knowledge_collections_collection_type",
            "knowledge_collections",
            ["collection_type"],
        )
        op.create_index(
            "ix_knowledge_collections_workspace_type",
            "knowledge_collections",
            ["workspace_id", "collection_type"],
        )

    if not _has_table(bind, "knowledge_documents"):
        op.create_table(
            "knowledge_documents",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("public_id", sa.String(length=24), nullable=False),
            sa.Column("workspace_id", sa.Integer(), nullable=False),
            sa.Column("collection_id", sa.Integer(), nullable=False),
            sa.Column("document_type", sa.String(length=32), nullable=False),
            sa.Column("title", sa.String(length=300), nullable=False),
            sa.Column("source_name", sa.String(length=160), nullable=True),
            sa.Column("source_uri", sa.String(length=600), nullable=True),
            sa.Column(
                "visibility", sa.String(length=16), nullable=False, server_default="workspace"
            ),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
            sa.Column("current_version", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("checksum", sa.String(length=64), nullable=True),
            sa.Column("language", sa.String(length=8), nullable=False, server_default="en"),
            sa.Column("industry", sa.String(length=80), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("archived_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
            sa.ForeignKeyConstraint(["collection_id"], ["knowledge_collections.id"]),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("public_id"),
        )
        op.create_index(
            "ix_knowledge_documents_workspace_id", "knowledge_documents", ["workspace_id"]
        )
        op.create_index(
            "ix_knowledge_documents_document_type", "knowledge_documents", ["document_type"]
        )
        op.create_index("ix_knowledge_documents_visibility", "knowledge_documents", ["visibility"])
        op.create_index("ix_knowledge_documents_status", "knowledge_documents", ["status"])
        op.create_index("ix_knowledge_documents_checksum", "knowledge_documents", ["checksum"])
        op.create_index("ix_knowledge_documents_industry", "knowledge_documents", ["industry"])
        op.create_index(
            "ix_knowledge_documents_created_by_user_id",
            "knowledge_documents",
            ["created_by_user_id"],
        )
        op.create_index(
            "ix_knowledge_documents_workspace_status",
            "knowledge_documents",
            ["workspace_id", "status"],
        )
        op.create_index(
            "ix_knowledge_documents_collection", "knowledge_documents", ["collection_id"]
        )

    if not _has_table(bind, "knowledge_document_versions"):
        op.create_table(
            "knowledge_document_versions",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("public_id", sa.String(length=24), nullable=False),
            sa.Column("workspace_id", sa.Integer(), nullable=False),
            sa.Column("document_id", sa.Integer(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("checksum", sa.String(length=64), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("content_chars", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_current", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
            sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("public_id"),
            sa.UniqueConstraint(
                "document_id", "version", name="uq_knowledge_document_versions_doc_version"
            ),
        )
        op.create_index(
            "ix_knowledge_document_versions_document_id",
            "knowledge_document_versions",
            ["document_id"],
        )
        op.create_index(
            "ix_knowledge_document_versions_checksum", "knowledge_document_versions", ["checksum"]
        )
        op.create_index(
            "ix_knowledge_document_versions_is_current",
            "knowledge_document_versions",
            ["is_current"],
        )
        op.create_index(
            "ix_knowledge_document_versions_workspace",
            "knowledge_document_versions",
            ["workspace_id"],
        )

    if not _has_table(bind, "knowledge_chunks"):
        op.create_table(
            "knowledge_chunks",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("public_id", sa.String(length=24), nullable=False),
            sa.Column("workspace_id", sa.Integer(), nullable=False),
            sa.Column("document_id", sa.Integer(), nullable=False),
            sa.Column("document_version_id", sa.Integer(), nullable=False),
            sa.Column("chunk_index", sa.Integer(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("embedding_json", sa.JSON(), nullable=True),
            sa.Column("embedding_model", sa.String(length=80), nullable=True),
            sa.Column("embedding_dim", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("embedding_norm", sa.Float(), nullable=False, server_default="0"),
            sa.Column("section", sa.String(length=300), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("is_active", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
            sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.id"]),
            sa.ForeignKeyConstraint(["document_version_id"], ["knowledge_document_versions.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("public_id"),
            sa.UniqueConstraint(
                "document_version_id", "chunk_index", name="uq_knowledge_chunks_version_index"
            ),
        )
        op.create_index("ix_knowledge_chunks_workspace_id", "knowledge_chunks", ["workspace_id"])
        op.create_index("ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"])
        op.create_index("ix_knowledge_chunks_is_active", "knowledge_chunks", ["is_active"])
        op.create_index(
            "ix_knowledge_chunks_workspace_active",
            "knowledge_chunks",
            ["workspace_id", "is_active"],
        )
        op.create_index(
            "ix_knowledge_chunks_document_version", "knowledge_chunks", ["document_version_id"]
        )

    if not _has_table(bind, "knowledge_ingestion_runs"):
        op.create_table(
            "knowledge_ingestion_runs",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("public_id", sa.String(length=24), nullable=False),
            sa.Column("workspace_id", sa.Integer(), nullable=False),
            sa.Column("document_id", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(length=24), nullable=False, server_default="queued"),
            sa.Column("trigger", sa.String(length=32), nullable=False, server_default="manual"),
            sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("embedding_provider", sa.String(length=32), nullable=True),
            sa.Column("embedding_model", sa.String(length=80), nullable=True),
            sa.Column("embedding_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("cost_micro_usd", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("latency_ms", sa.Integer(), nullable=True),
            sa.Column("error_code", sa.String(length=64), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("trace_id", sa.String(length=64), nullable=False),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
            sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.id"]),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("public_id"),
        )
        op.create_index(
            "ix_knowledge_ingestion_runs_workspace_id",
            "knowledge_ingestion_runs",
            ["workspace_id"],
        )
        op.create_index(
            "ix_knowledge_ingestion_runs_document_id", "knowledge_ingestion_runs", ["document_id"]
        )
        op.create_index("ix_knowledge_ingestion_runs_status", "knowledge_ingestion_runs", ["status"])
        op.create_index(
            "ix_knowledge_ingestion_runs_workspace_created",
            "knowledge_ingestion_runs",
            ["workspace_id", "created_at"],
        )


def downgrade() -> None:
    bind = None if context.is_offline_mode() else op.get_bind()
    if bind is None:
        return
    for table in _TABLES:
        if _has_table(bind, table):
            op.drop_table(table)
