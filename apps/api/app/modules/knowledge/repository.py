from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.modules.knowledge.models import (
    KnowledgeChunk,
    KnowledgeCollection,
    KnowledgeDocument,
    KnowledgeDocumentVersion,
    KnowledgeIngestionRun,
)
from app.modules.knowledge.visibility import visibility_clause


class KnowledgeRepository:
    """Persistence for the sales knowledge store.

    Every read method takes a workspace_id and applies it in the query. There
    is deliberately no "get by public id" that omits the workspace: a caller
    must not be able to reach another tenant's row even by guessing an
    identifier.
    """

    # --- collections ---------------------------------------------------

    def create_collection(
        self,
        db: Session,
        *,
        workspace_id: int,
        slug: str,
        name: str,
        collection_type: str,
        description: str | None,
    ) -> KnowledgeCollection:
        collection = KnowledgeCollection(
            workspace_id=workspace_id,
            slug=slug,
            name=name,
            collection_type=collection_type,
            description=description,
        )
        db.add(collection)
        db.commit()
        db.refresh(collection)
        return collection

    def get_collection(
        self, db: Session, *, workspace_id: int, collection_id: str
    ) -> KnowledgeCollection | None:
        return db.scalar(
            select(KnowledgeCollection).where(
                KnowledgeCollection.workspace_id == workspace_id,
                KnowledgeCollection.public_id == collection_id,
            )
        )

    def get_collection_by_slug(
        self, db: Session, *, workspace_id: int, slug: str
    ) -> KnowledgeCollection | None:
        return db.scalar(
            select(KnowledgeCollection).where(
                KnowledgeCollection.workspace_id == workspace_id,
                KnowledgeCollection.slug == slug,
            )
        )

    def list_collections(self, db: Session, *, workspace_id: int) -> list[KnowledgeCollection]:
        return list(
            db.scalars(
                select(KnowledgeCollection)
                .where(KnowledgeCollection.workspace_id == workspace_id)
                .order_by(KnowledgeCollection.id)
            )
        )

    def count_documents(self, db: Session, *, workspace_id: int, collection_id: int) -> int:
        return int(
            db.scalar(
                select(func.count(KnowledgeDocument.id)).where(
                    KnowledgeDocument.workspace_id == workspace_id,
                    KnowledgeDocument.collection_id == collection_id,
                )
            )
            or 0
        )

    # --- documents -----------------------------------------------------

    def create_document(
        self,
        db: Session,
        *,
        workspace_id: int,
        collection_id: int,
        document_type: str,
        title: str,
        source_name: str | None,
        source_uri: str | None,
        visibility: str,
        language: str,
        industry: str | None,
        metadata: dict[str, Any],
        created_by_user_id: int | None,
    ) -> KnowledgeDocument:
        document = KnowledgeDocument(
            workspace_id=workspace_id,
            collection_id=collection_id,
            document_type=document_type,
            title=title,
            source_name=source_name,
            source_uri=source_uri,
            visibility=visibility,
            language=language,
            industry=industry,
            metadata_json=metadata,
            created_by_user_id=created_by_user_id,
            status="draft",
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        return document

    def get_document(
        self, db: Session, *, workspace_id: int, document_id: str
    ) -> KnowledgeDocument | None:
        return db.scalar(
            select(KnowledgeDocument).where(
                KnowledgeDocument.workspace_id == workspace_id,
                KnowledgeDocument.public_id == document_id,
            )
        )

    def list_documents(
        self,
        db: Session,
        *,
        workspace_id: int,
        user_id: int | None,
        user_role: str | None,
        collection_id: int | None = None,
        limit: int = 100,
    ) -> list[KnowledgeDocument]:
        stmt = select(KnowledgeDocument).where(
            KnowledgeDocument.workspace_id == workspace_id,
            visibility_clause(user_id=user_id, user_role=user_role),
        )
        if collection_id is not None:
            stmt = stmt.where(KnowledgeDocument.collection_id == collection_id)
        stmt = stmt.order_by(KnowledgeDocument.id.desc()).limit(limit)
        return list(db.scalars(stmt))

    def set_document_status(
        self, db: Session, *, document: KnowledgeDocument, status: str
    ) -> KnowledgeDocument:
        document.status = status
        if status == "archived":
            document.archived_at = datetime.now(tz=UTC)
        db.add(document)
        db.commit()
        db.refresh(document)
        return document

    def archive_document(
        self, db: Session, *, workspace_id: int, document: KnowledgeDocument
    ) -> None:
        """Archive a document and deactivate its chunks in one transaction.

        Deactivating the chunks is what actually removes it from retrieval.
        The status change alone would be enough given the retrieval join, but
        doing both means a single missed predicate cannot resurrect archived
        content.
        """
        document.status = "archived"
        document.archived_at = datetime.now(tz=UTC)
        db.add(document)
        db.execute(
            update(KnowledgeChunk)
            .where(
                KnowledgeChunk.workspace_id == workspace_id,
                KnowledgeChunk.document_id == document.id,
            )
            .values(is_active=False)
        )
        db.commit()

    # --- versions ------------------------------------------------------

    def next_version_number(self, db: Session, *, document_id: int) -> int:
        current = db.scalar(
            select(func.max(KnowledgeDocumentVersion.version)).where(
                KnowledgeDocumentVersion.document_id == document_id
            )
        )
        return int(current or 0) + 1

    def get_current_version(
        self, db: Session, *, workspace_id: int, document_id: int
    ) -> KnowledgeDocumentVersion | None:
        return db.scalar(
            select(KnowledgeDocumentVersion).where(
                KnowledgeDocumentVersion.workspace_id == workspace_id,
                KnowledgeDocumentVersion.document_id == document_id,
                KnowledgeDocumentVersion.is_current.is_(True),
            )
        )

    def create_version(
        self,
        db: Session,
        *,
        workspace_id: int,
        document_id: int,
        version: int,
        checksum: str,
        content: str,
    ) -> KnowledgeDocumentVersion:
        record = KnowledgeDocumentVersion(
            workspace_id=workspace_id,
            document_id=document_id,
            version=version,
            checksum=checksum,
            content=content,
            content_chars=len(content),
            is_current=False,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def activate_version(
        self,
        db: Session,
        *,
        workspace_id: int,
        document: KnowledgeDocument,
        version: KnowledgeDocumentVersion,
        chunk_count: int,
    ) -> None:
        """Make this version the retrievable one, atomically.

        The previous version's chunks are deactivated and the new version's
        activated in the same transaction, so a search can never see two
        versions of the same document at once, nor zero of them.
        """
        db.execute(
            update(KnowledgeChunk)
            .where(
                KnowledgeChunk.workspace_id == workspace_id,
                KnowledgeChunk.document_id == document.id,
                KnowledgeChunk.document_version_id != version.id,
            )
            .values(is_active=False)
        )
        db.execute(
            update(KnowledgeDocumentVersion)
            .where(
                KnowledgeDocumentVersion.workspace_id == workspace_id,
                KnowledgeDocumentVersion.document_id == document.id,
                KnowledgeDocumentVersion.id != version.id,
            )
            .values(is_current=False)
        )
        db.execute(
            update(KnowledgeChunk)
            .where(
                KnowledgeChunk.workspace_id == workspace_id,
                KnowledgeChunk.document_version_id == version.id,
            )
            .values(is_active=True)
        )
        version.is_current = True
        version.chunk_count = chunk_count
        document.current_version = version.version
        document.checksum = version.checksum
        document.status = "ready"
        db.add(version)
        db.add(document)
        db.commit()

    # --- chunks --------------------------------------------------------

    def add_chunks(self, db: Session, *, chunks: list[KnowledgeChunk]) -> None:
        if not chunks:
            return
        db.add_all(chunks)
        db.commit()

    def count_active_chunks(self, db: Session, *, workspace_id: int, document_id: int) -> int:
        return int(
            db.scalar(
                select(func.count(KnowledgeChunk.id)).where(
                    KnowledgeChunk.workspace_id == workspace_id,
                    KnowledgeChunk.document_id == document_id,
                    KnowledgeChunk.is_active.is_(True),
                )
            )
            or 0
        )

    # --- ingestion runs -------------------------------------------------

    def create_ingestion_run(
        self,
        db: Session,
        *,
        workspace_id: int,
        document_id: int | None,
        trigger: str,
        created_by_user_id: int | None,
        trace_id: str | None = None,
    ) -> KnowledgeIngestionRun:
        run = KnowledgeIngestionRun(
            workspace_id=workspace_id,
            document_id=document_id,
            trigger=trigger,
            created_by_user_id=created_by_user_id,
            status="running",
        )
        if trace_id:
            run.trace_id = trace_id
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    def finish_ingestion_run(
        self,
        db: Session,
        *,
        run: KnowledgeIngestionRun,
        status: str,
        chunk_count: int = 0,
        embedding_provider: str | None = None,
        embedding_model: str | None = None,
        embedding_tokens: int = 0,
        cost_micro_usd: int = 0,
        latency_ms: int | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> KnowledgeIngestionRun:
        run.status = status
        run.chunk_count = chunk_count
        run.embedding_provider = embedding_provider
        run.embedding_model = embedding_model
        run.embedding_tokens = embedding_tokens
        run.cost_micro_usd = cost_micro_usd
        run.latency_ms = latency_ms
        run.error_code = error_code
        run.error_message = error_message
        run.completed_at = datetime.now(tz=UTC)
        db.add(run)
        db.commit()
        db.refresh(run)
        return run


__all__ = ["KnowledgeRepository"]
