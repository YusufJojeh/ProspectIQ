from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.modules.knowledge.constants import CollectionType, Visibility


class CollectionCreateRequest(BaseModel):
    slug: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    name: str = Field(min_length=1, max_length=160)
    collection_type: CollectionType
    description: str | None = Field(default=None, max_length=2000)


class CollectionResponse(BaseModel):
    collection_id: str
    slug: str
    name: str
    collection_type: str
    description: str | None
    document_count: int
    created_at: datetime


class CollectionListResponse(BaseModel):
    collections: list[CollectionResponse] = Field(default_factory=list)


class DocumentCreateRequest(BaseModel):
    collection_id: str
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1)
    source_name: str | None = Field(default=None, max_length=160)
    source_uri: str | None = Field(default=None, max_length=600)
    visibility: Visibility = "workspace"
    language: str = Field(default="en", max_length=8)
    industry: str | None = Field(default=None, max_length=80)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentResponse(BaseModel):
    document_id: str
    collection_id: str
    document_type: str
    title: str
    source_name: str | None
    visibility: str
    status: str
    current_version: int
    chunk_count: int
    language: str
    industry: str | None
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse] = Field(default_factory=list)


class IngestionResponse(BaseModel):
    """Outcome of one ingestion attempt.

    `skipped_unchanged` is reported explicitly rather than silently: it is the
    difference between "we re-embedded 400 chunks" and "the checksum matched
    and we spent nothing".
    """

    ingestion_id: str
    document_id: str
    status: str
    version: int
    chunk_count: int
    embedding_provider: str | None
    embedding_model: str | None
    embedding_tokens: int
    fallback_used: bool
    latency_ms: int | None
    error_code: str | None
    error_message: str | None
    trace_id: str


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    collection_types: list[CollectionType] | None = None
    industry: str | None = Field(default=None, max_length=80)
    limit: int | None = Field(default=None, ge=1, le=100)


class KnowledgeCitation(BaseModel):
    """A citation the caller (or a human reviewer) can resolve back to source.

    Every retrieved passage carries the document and chunk it came from, so a
    claim in a generated draft is always traceable to an approved internal
    document rather than to the model's memory.
    """

    chunk_id: str
    document_id: str
    document_title: str
    document_type: str
    section: str | None
    version: int
    excerpt: str
    score: float
    vector_score: float
    keyword_score: float


class KnowledgeSearchResponse(BaseModel):
    query: str
    results: list[KnowledgeCitation] = Field(default_factory=list)
    candidate_count: int
    embedding_model: str | None
    degraded: bool = False


__all__ = [
    "CollectionCreateRequest",
    "CollectionListResponse",
    "CollectionResponse",
    "DocumentCreateRequest",
    "DocumentListResponse",
    "DocumentResponse",
    "IngestionResponse",
    "KnowledgeCitation",
    "KnowledgeSearchRequest",
    "KnowledgeSearchResponse",
]
