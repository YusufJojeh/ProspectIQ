from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.modules.knowledge.constants import (
    COLLECTION_TYPES,
    RESTRICTED_ROLES,
    VISIBILITY_RESTRICTED,
)
from app.modules.knowledge.ingestion import KnowledgeIngestionService
from app.modules.knowledge.models import KnowledgeCollection, KnowledgeDocument
from app.modules.knowledge.repository import KnowledgeRepository
from app.modules.knowledge.retrieval import KnowledgeRetriever, excerpt
from app.modules.knowledge.schemas import (
    CollectionCreateRequest,
    CollectionResponse,
    DocumentCreateRequest,
    DocumentResponse,
    IngestionResponse,
    KnowledgeCitation,
    KnowledgeSearchResponse,
)
from app.modules.knowledge.visibility import can_view


@dataclass
class KnowledgeService:
    """Application layer for the sales knowledge store.

    The agent never reaches this class directly with a workspace of its
    choosing: the workspace always arrives from the authenticated request or
    from the agent run's own row, never from a tool argument.
    """

    repository: KnowledgeRepository = field(default_factory=KnowledgeRepository)
    ingestion: KnowledgeIngestionService = field(default_factory=KnowledgeIngestionService)
    retriever: KnowledgeRetriever = field(default_factory=KnowledgeRetriever)
    settings: Settings = field(default_factory=get_settings)

    # --- collections ---------------------------------------------------

    def create_collection(
        self, db: Session, *, workspace_id: int, payload: CollectionCreateRequest
    ) -> CollectionResponse:
        existing = self.repository.get_collection_by_slug(
            db, workspace_id=workspace_id, slug=payload.slug
        )
        if existing is not None:
            raise ConflictError(f"A collection with slug '{payload.slug}' already exists.")
        collection = self.repository.create_collection(
            db,
            workspace_id=workspace_id,
            slug=payload.slug,
            name=payload.name,
            collection_type=payload.collection_type,
            description=payload.description,
        )
        return self._collection_response(db, workspace_id=workspace_id, collection=collection)

    def list_collections(self, db: Session, *, workspace_id: int) -> list[CollectionResponse]:
        return [
            self._collection_response(db, workspace_id=workspace_id, collection=collection)
            for collection in self.repository.list_collections(db, workspace_id=workspace_id)
        ]

    # --- documents -----------------------------------------------------

    def create_document(
        self,
        db: Session,
        *,
        workspace_id: int,
        user_id: int,
        user_role: str,
        payload: DocumentCreateRequest,
    ) -> tuple[DocumentResponse, IngestionResponse]:
        if payload.visibility == VISIBILITY_RESTRICTED and user_role not in RESTRICTED_ROLES:
            # A caller may not create content they would not be allowed to read back.
            raise ForbiddenError("Your role cannot create restricted knowledge documents.")
        collection = self.repository.get_collection(
            db, workspace_id=workspace_id, collection_id=payload.collection_id
        )
        if collection is None:
            raise NotFoundError("Collection not found.")

        document = self.repository.create_document(
            db,
            workspace_id=workspace_id,
            collection_id=collection.id,
            document_type=collection.collection_type,
            title=payload.title,
            source_name=payload.source_name,
            source_uri=payload.source_uri,
            visibility=payload.visibility,
            language=payload.language,
            industry=payload.industry,
            metadata=payload.metadata,
            created_by_user_id=user_id,
        )
        outcome = self.ingestion.ingest(
            db,
            workspace_id=workspace_id,
            document=document,
            content=payload.content,
            trigger="api",
            created_by_user_id=user_id,
        )
        db.refresh(document)
        return (
            self._document_response(db, workspace_id=workspace_id, document=document),
            IngestionResponse(
                ingestion_id=outcome.run.public_id,
                document_id=document.public_id,
                status=outcome.run.status,
                version=outcome.version,
                chunk_count=outcome.chunk_count,
                embedding_provider=outcome.run.embedding_provider,
                embedding_model=outcome.run.embedding_model,
                embedding_tokens=outcome.run.embedding_tokens,
                fallback_used=outcome.fallback_used,
                latency_ms=outcome.run.latency_ms,
                error_code=outcome.run.error_code,
                error_message=outcome.run.error_message,
                trace_id=outcome.run.trace_id,
            ),
        )

    def reingest_document(
        self,
        db: Session,
        *,
        workspace_id: int,
        user_id: int,
        user_role: str,
        document_id: str,
        content: str,
    ) -> IngestionResponse:
        document = self._get_visible_document(
            db, workspace_id=workspace_id, document_id=document_id, user_id=user_id, user_role=user_role
        )
        outcome = self.ingestion.ingest(
            db,
            workspace_id=workspace_id,
            document=document,
            content=content,
            trigger="reingest",
            created_by_user_id=user_id,
        )
        return IngestionResponse(
            ingestion_id=outcome.run.public_id,
            document_id=document.public_id,
            status=outcome.run.status,
            version=outcome.version,
            chunk_count=outcome.chunk_count,
            embedding_provider=outcome.run.embedding_provider,
            embedding_model=outcome.run.embedding_model,
            embedding_tokens=outcome.run.embedding_tokens,
            fallback_used=outcome.fallback_used,
            latency_ms=outcome.run.latency_ms,
            error_code=outcome.run.error_code,
            error_message=outcome.run.error_message,
            trace_id=outcome.run.trace_id,
        )

    def list_documents(
        self,
        db: Session,
        *,
        workspace_id: int,
        user_id: int | None,
        user_role: str | None,
        collection_id: str | None = None,
    ) -> list[DocumentResponse]:
        """Only documents the caller may see; the identity is a required argument
        so no caller can accidentally list the whole workspace."""
        internal_collection_id: int | None = None
        if collection_id:
            collection = self.repository.get_collection(
                db, workspace_id=workspace_id, collection_id=collection_id
            )
            if collection is None:
                raise NotFoundError("Collection not found.")
            internal_collection_id = collection.id
        return [
            self._document_response(db, workspace_id=workspace_id, document=document)
            for document in self.repository.list_documents(
                db,
                workspace_id=workspace_id,
                user_id=user_id,
                user_role=user_role,
                collection_id=internal_collection_id,
            )
        ]

    def archive_document(
        self,
        db: Session,
        *,
        workspace_id: int,
        user_id: int,
        user_role: str,
        document_id: str,
    ) -> None:
        document = self._get_visible_document(
            db, workspace_id=workspace_id, document_id=document_id, user_id=user_id, user_role=user_role
        )
        self.repository.archive_document(db, workspace_id=workspace_id, document=document)

    def _get_visible_document(
        self,
        db: Session,
        *,
        workspace_id: int,
        document_id: str,
        user_id: int,
        user_role: str,
    ) -> KnowledgeDocument:
        """A document the caller may not see is reported as missing, not forbidden,
        so its existence is not disclosed."""
        document = self.repository.get_document(
            db, workspace_id=workspace_id, document_id=document_id
        )
        if document is None or not can_view(document, user_id=user_id, user_role=user_role):
            raise NotFoundError("Document not found.")
        return document

    # --- retrieval -----------------------------------------------------

    def search(
        self,
        db: Session,
        *,
        workspace_id: int,
        query: str,
        user_id: int | None,
        user_role: str | None,
        collection_types: list[str] | None = None,
        industry: str | None = None,
        limit: int | None = None,
    ) -> KnowledgeSearchResponse:
        document_types = self._validated_types(collection_types)
        outcome = self.retriever.search(
            db,
            workspace_id=workspace_id,
            query=query,
            user_id=user_id,
            user_role=user_role,
            document_types=document_types,
            industry=industry,
            limit=limit,
        )
        return KnowledgeSearchResponse(
            query=query,
            results=[
                KnowledgeCitation(
                    chunk_id=item.chunk_id,
                    document_id=item.document_id,
                    document_title=item.document_title,
                    document_type=item.document_type,
                    section=item.section,
                    version=item.version,
                    excerpt=excerpt(
                        item.content, max_chars=self.settings.knowledge_excerpt_max_chars
                    ),
                    score=item.score,
                    vector_score=item.vector_score,
                    keyword_score=item.keyword_score,
                )
                for item in outcome.results
            ],
            candidate_count=outcome.candidate_count,
            embedding_model=outcome.embedding_model,
            degraded=outcome.degraded,
        )

    # --- helpers -------------------------------------------------------

    def _validated_types(self, collection_types: list[str] | None) -> tuple[str, ...] | None:
        """Drop anything not in the closed set.

        The agent supplies these values, so an unknown type is ignored rather
        than trusted: a filter it invents must never widen what it can reach.
        """
        if not collection_types:
            return None
        allowed = tuple(value for value in collection_types if value in COLLECTION_TYPES)
        return allowed or None

    def _collection_response(
        self, db: Session, *, workspace_id: int, collection: KnowledgeCollection
    ) -> CollectionResponse:
        return CollectionResponse(
            collection_id=collection.public_id,
            slug=collection.slug,
            name=collection.name,
            collection_type=collection.collection_type,
            description=collection.description,
            document_count=self.repository.count_documents(
                db, workspace_id=workspace_id, collection_id=collection.id
            ),
            created_at=collection.created_at,
        )

    def _document_response(
        self, db: Session, *, workspace_id: int, document: KnowledgeDocument
    ) -> DocumentResponse:
        collection = db.get(KnowledgeCollection, document.collection_id)
        return DocumentResponse(
            document_id=document.public_id,
            collection_id=collection.public_id if collection else "",
            document_type=document.document_type,
            title=document.title,
            source_name=document.source_name,
            visibility=document.visibility,
            status=document.status,
            current_version=document.current_version,
            chunk_count=self.repository.count_active_chunks(
                db, workspace_id=workspace_id, document_id=document.id
            ),
            language=document.language,
            industry=document.industry,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )


__all__ = ["KnowledgeService"]
