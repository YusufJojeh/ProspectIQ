from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.utils.identifiers import new_public_id

# --- Sales Knowledge RAG ------------------------------------------------
#
# This module answers a different question from lead research. Lead
# research establishes "what is true about the prospect?" and stays in the
# leads/research/evidence tables. Sales Knowledge answers "what can WE
# credibly offer this prospect?" -- our service catalogue, case studies,
# playbooks, objection handling, approved proposal templates.
#
# The two are never mixed. Structured operational lead data (score,
# evidence, stage, CRM fields, research history) is NOT embedded into this
# store just because vectors are available; it continues to be read through
# ordinary deterministic tools. What lives here is unstructured or
# semi-structured internal knowledge that only similarity search can
# usefully retrieve.


class KnowledgeCollection(Base):
    """A named grouping of documents of one kind (case_studies, services,
    playbooks, ...). Collections are the unit the agent filters on, so the
    model can ask for "case studies about healthcare" without being able to
    reach documents of a kind it was not offered.
    """

    __tablename__ = "knowledge_collections"
    __table_args__ = (
        UniqueConstraint("workspace_id", "slug", name="uq_knowledge_collections_workspace_slug"),
        Index("ix_knowledge_collections_workspace_type", "workspace_id", "collection_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(24), unique=True, default=lambda: new_public_id("kcol")
    )
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    slug: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(160))
    #: One of knowledge.constants.COLLECTION_TYPES.
    collection_type: Mapped[str] = mapped_column(String(32), index=True)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    is_active: Mapped[bool] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), default=lambda: datetime.now(tz=UTC), onupdate=lambda: datetime.now(tz=UTC)
    )


class KnowledgeDocument(Base):
    """One logical document. Its text lives in versions, not here, so a
    re-ingestion produces a new KnowledgeDocumentVersion and the document's
    identity (and any citation pointing at it) survives.

    `status` gates retrieval: only 'ready' documents are searchable.
    Archiving or deleting a document must immediately stop its chunks being
    retrievable -- that is enforced in the retrieval SQL, not afterwards in
    Python.
    """

    __tablename__ = "knowledge_documents"
    __table_args__ = (
        Index("ix_knowledge_documents_workspace_status", "workspace_id", "status"),
        Index("ix_knowledge_documents_collection", "collection_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(24), unique=True, default=lambda: new_public_id("kdoc")
    )
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    collection_id: Mapped[int] = mapped_column(ForeignKey("knowledge_collections.id"))
    #: Denormalized from the collection so retrieval can filter by document
    #: type without a join, and so a document keeps its type if it is ever
    #: moved between collections.
    document_type: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(300))
    source_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    #: Only ever a safe, workspace-supplied reference (an internal path or a
    #: URL the workspace itself provided). Never fetched by the agent.
    source_uri: Mapped[str | None] = mapped_column(String(600), nullable=True)
    #: workspace | private | restricted -- see knowledge.constants.
    visibility: Mapped[str] = mapped_column(String(16), default="workspace", index=True)
    #: draft | ingesting | ready | failed | archived
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    current_version: Mapped[int] = mapped_column(Integer, default=0)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    language: Mapped[str] = mapped_column(String(8), default="en")
    industry: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON(), default=dict)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), default=lambda: datetime.now(tz=UTC), onupdate=lambda: datetime.now(tz=UTC)
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)


class KnowledgeDocumentVersion(Base):
    """One immutable ingested revision of a document's text.

    Keeping versions rather than overwriting is what makes "which version
    did that answer cite?" answerable months later, and lets a superseded
    version's chunks be deactivated atomically when a new one goes live.
    """

    __tablename__ = "knowledge_document_versions"
    __table_args__ = (
        UniqueConstraint(
            "document_id", "version", name="uq_knowledge_document_versions_doc_version"
        ),
        Index("ix_knowledge_document_versions_workspace", "workspace_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(24), unique=True, default=lambda: new_public_id("kver")
    )
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("knowledge_documents.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64), index=True)
    content: Mapped[str] = mapped_column(Text())
    content_chars: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    #: True only for the version currently serving retrieval.
    is_current: Mapped[bool] = mapped_column(Integer, default=0, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))


class KnowledgeChunk(Base):
    """One embedded, retrievable passage.

    The embedding is stored as a JSON array of floats rather than a native
    vector column: the deployment database is MariaDB/MySQL, where pgvector
    is not available. Similarity is therefore computed in the application
    over a candidate set that the SQL query has ALREADY restricted by
    workspace, visibility, document status and collection type -- a chunk
    from another tenant is never loaded, let alone scored. `embedding_dim`
    and `embedding_model` are stored per row so a model change cannot
    silently mix incompatible vector spaces.
    """

    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        Index("ix_knowledge_chunks_workspace_active", "workspace_id", "is_active"),
        Index("ix_knowledge_chunks_document_version", "document_version_id"),
        UniqueConstraint(
            "document_version_id", "chunk_index", name="uq_knowledge_chunks_version_index"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(24), unique=True, default=lambda: new_public_id("kchk")
    )
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("knowledge_documents.id"), index=True)
    document_version_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_document_versions.id")
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text())
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    embedding_json: Mapped[list[float] | None] = mapped_column(JSON(), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    embedding_dim: Mapped[int] = mapped_column(Integer, default=0)
    #: Precomputed L2 norm, so cosine similarity is one dot product per
    #: candidate instead of two full passes.
    embedding_norm: Mapped[float] = mapped_column(Float(), default=0.0)
    #: Section/heading context preserved so a chunk boundary never destroys
    #: which service or case study the passage belongs to.
    section: Mapped[str | None] = mapped_column(String(300), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON(), default=dict)
    is_active: Mapped[bool] = mapped_column(Integer, default=1, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))


class KnowledgeIngestionRun(Base):
    """Audit record for one ingestion attempt, successful or not.

    Carries the same trace_id as the agent/research run that triggered it
    when there is one, so an ingestion is reconstructable alongside
    everything else in the system.
    """

    __tablename__ = "knowledge_ingestion_runs"
    __table_args__ = (
        Index("ix_knowledge_ingestion_runs_workspace_created", "workspace_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(24), unique=True, default=lambda: new_public_id("king")
    )
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_documents.id"), nullable=True, index=True
    )
    #: queued | running | completed | skipped_unchanged | failed
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    trigger: Mapped[str] = mapped_column(String(32), default="manual")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    embedding_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    embedding_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_micro_usd: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    trace_id: Mapped[str] = mapped_column(String(64), default=lambda: new_public_id("trace"))
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)


__all__ = [
    "KnowledgeChunk",
    "KnowledgeCollection",
    "KnowledgeDocument",
    "KnowledgeDocumentVersion",
    "KnowledgeIngestionRun",
]
