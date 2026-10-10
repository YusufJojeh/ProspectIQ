from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import ApiError
from app.modules.ai_runtime.usage import OPERATION_EMBEDDING, UsageLedger
from app.modules.knowledge.chunking import chunk_document, sanitize_text
from app.modules.knowledge.embeddings import EmbeddingRouter, vector_norm
from app.modules.knowledge.models import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeIngestionRun,
)
from app.modules.knowledge.repository import KnowledgeRepository

logger = logging.getLogger(__name__)

STATUS_COMPLETED = "completed"
STATUS_SKIPPED = "skipped_unchanged"
STATUS_FAILED = "failed"


@dataclass(frozen=True, slots=True)
class IngestionOutcome:
    run: KnowledgeIngestionRun
    document: KnowledgeDocument
    version: int
    chunk_count: int
    fallback_used: bool


def checksum_for(content: str) -> str:
    return hashlib.sha256(sanitize_text(content).encode("utf-8")).hexdigest()


@dataclass
class KnowledgeIngestionService:
    """Validate, chunk, embed and index one document.

    The pipeline is deliberately linear and fully audited:

        validate -> sanitize -> checksum -> (skip if unchanged) -> version
        -> chunk -> embed -> store chunks -> activate version -> mark ready

    Two decisions are worth naming. First, a document whose sanitized content
    checksums to what is already live is skipped rather than re-embedded:
    re-ingesting an unchanged 200-page playbook nightly is the easiest way to
    burn an embedding budget for nothing. Second, chunks are written while
    the previous version is still the live one, and the swap happens in a
    single transaction at the end -- so a failure halfway through leaves the
    old version serving rather than leaving the document unsearchable.
    """

    repository: KnowledgeRepository = field(default_factory=KnowledgeRepository)
    embeddings: EmbeddingRouter = field(default_factory=EmbeddingRouter)
    settings: Settings = field(default_factory=get_settings)
    usage: UsageLedger = field(default_factory=UsageLedger)

    def ingest(
        self,
        db: Session,
        *,
        workspace_id: int,
        document: KnowledgeDocument,
        content: str,
        trigger: str = "manual",
        created_by_user_id: int | None = None,
        trace_id: str | None = None,
    ) -> IngestionOutcome:
        started = time.monotonic()
        run = self.repository.create_ingestion_run(
            db,
            workspace_id=workspace_id,
            document_id=document.id,
            trigger=trigger,
            created_by_user_id=created_by_user_id,
            trace_id=trace_id,
        )

        try:
            cleaned = self._validate(content)
            digest = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()

            current = self.repository.get_current_version(
                db, workspace_id=workspace_id, document_id=document.id
            )
            if current is not None and current.checksum == digest:
                self.repository.finish_ingestion_run(
                    db,
                    run=run,
                    status=STATUS_SKIPPED,
                    chunk_count=current.chunk_count,
                    latency_ms=int((time.monotonic() - started) * 1000),
                )
                return IngestionOutcome(
                    run=run,
                    document=document,
                    version=current.version,
                    chunk_count=current.chunk_count,
                    fallback_used=False,
                )

            self.repository.set_document_status(db, document=document, status="ingesting")

            chunks = chunk_document(
                cleaned,
                target_chars=self.settings.knowledge_chunk_target_chars,
                overlap_chars=self.settings.knowledge_chunk_overlap_chars,
                max_chars=self.settings.knowledge_chunk_max_chars,
                max_chunks=self.settings.knowledge_max_chunks_per_document,
                base_metadata={"document_type": document.document_type},
            )
            if not chunks:
                raise ApiError("Document produced no indexable content.")

            version_number = self.repository.next_version_number(db, document_id=document.id)
            version = self.repository.create_version(
                db,
                workspace_id=workspace_id,
                document_id=document.id,
                version=version_number,
                checksum=digest,
                content=cleaned,
            )

            embedded_vectors: list[list[float]] = []
            provider = model = None
            total_tokens = 0
            fallback_used = False
            batch_size = self.settings.embedding_batch_size
            for start in range(0, len(chunks), batch_size):
                batch = chunks[start : start + batch_size]
                result = self.embeddings.embed([chunk.content for chunk in batch])
                # Every embedding batch is a billable provider call, so it
                # goes in the same ledger as model calls -- including the
                # failed one below, which costs latency and sometimes money.
                self.usage.record(
                    db,
                    workspace_id=workspace_id,
                    trace_id=run.trace_id or run.public_id,
                    operation=OPERATION_EMBEDDING,
                    subject_id=run.public_id,
                    provider=result.provider,
                    model=result.model,
                    embedding_tokens=result.tokens,
                    latency_ms=result.latency_ms,
                    status="ok" if result.ok else "error",
                    fallback_from=result.model if result.fallback_used else None,
                    error_message=result.error,
                )
                if not result.ok:
                    raise ApiError(f"Embedding failed: {result.error or 'unknown error'}")
                embedded_vectors.extend(result.vectors)
                provider = result.provider
                model = result.model
                total_tokens += result.tokens
                fallback_used = fallback_used or result.fallback_used

            records = [
                KnowledgeChunk(
                    workspace_id=workspace_id,
                    document_id=document.id,
                    document_version_id=version.id,
                    chunk_index=chunk.index,
                    content=chunk.content,
                    token_count=chunk.token_count,
                    embedding_json=vector,
                    embedding_model=model,
                    embedding_dim=len(vector),
                    embedding_norm=vector_norm(vector),
                    section=chunk.section[:300] if chunk.section else None,
                    metadata_json=chunk.metadata,
                    # Written inactive: the previous version keeps serving
                    # until activate_version swaps them together.
                    is_active=False,
                )
                for chunk, vector in zip(chunks, embedded_vectors, strict=True)
            ]
            self.repository.add_chunks(db, chunks=records)
            self.repository.activate_version(
                db,
                workspace_id=workspace_id,
                document=document,
                version=version,
                chunk_count=len(records),
            )

            self.repository.finish_ingestion_run(
                db,
                run=run,
                status=STATUS_COMPLETED,
                chunk_count=len(records),
                embedding_provider=provider,
                embedding_model=model,
                embedding_tokens=total_tokens,
                latency_ms=int((time.monotonic() - started) * 1000),
            )
            return IngestionOutcome(
                run=run,
                document=document,
                version=version_number,
                chunk_count=len(records),
                fallback_used=fallback_used,
            )

        except ApiError as exc:
            self._fail(db, run=run, document=document, code="ingestion_failed", message=str(exc))
            raise
        except Exception as exc:  # noqa: BLE001 - recorded, then re-raised
            logger.exception("knowledge.ingestion.unhandled document_id=%s", document.public_id)
            self._fail(db, run=run, document=document, code="internal_error", message=str(exc))
            raise

    def _validate(self, content: str) -> str:
        cleaned = sanitize_text(content)
        if not cleaned:
            raise ApiError("Document content is empty.")
        if len(cleaned) > self.settings.knowledge_max_document_chars:
            raise ApiError(
                "Document exceeds the maximum indexable size of "
                f"{self.settings.knowledge_max_document_chars} characters."
            )
        return cleaned

    def _fail(
        self,
        db: Session,
        *,
        run: KnowledgeIngestionRun,
        document: KnowledgeDocument,
        code: str,
        message: str,
    ) -> None:
        db.rollback()
        self.repository.set_document_status(
            db,
            document=document,
            # A document that has a live version stays ready and keeps
            # serving it; only a never-ingested one becomes 'failed'.
            status="ready" if document.current_version else "failed",
        )
        self.repository.finish_ingestion_run(
            db,
            run=run,
            status=STATUS_FAILED,
            error_code=code,
            error_message=message[:2000],
        )


__all__ = [
    "STATUS_COMPLETED",
    "STATUS_FAILED",
    "STATUS_SKIPPED",
    "IngestionOutcome",
    "KnowledgeIngestionService",
    "checksum_for",
]
