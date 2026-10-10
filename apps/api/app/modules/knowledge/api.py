from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.policies import get_current_user, get_current_workspace_id
from app.modules.knowledge.schemas import (
    CollectionCreateRequest,
    CollectionListResponse,
    CollectionResponse,
    DocumentCreateRequest,
    DocumentListResponse,
    IngestionResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
)
from app.modules.knowledge.service import KnowledgeService
from app.modules.users.models import User

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])

_service = KnowledgeService()


@router.post("/collections", response_model=CollectionResponse, status_code=status.HTTP_201_CREATED)
def create_collection(
    payload: CollectionCreateRequest,
    db: Session = Depends(get_db),
    workspace_id: int = Depends(get_current_workspace_id),
) -> CollectionResponse:
    return _service.create_collection(db, workspace_id=workspace_id, payload=payload)


@router.get("/collections", response_model=CollectionListResponse)
def list_collections(
    db: Session = Depends(get_db),
    workspace_id: int = Depends(get_current_workspace_id),
) -> CollectionListResponse:
    return CollectionListResponse(
        collections=_service.list_collections(db, workspace_id=workspace_id)
    )


@router.post("/documents", response_model=IngestionResponse, status_code=status.HTTP_201_CREATED)
def create_document(
    payload: DocumentCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> IngestionResponse:
    _document, ingestion = _service.create_document(
        db, workspace_id=user.workspace_id, user_id=user.id, user_role=user.role, payload=payload
    )
    return ingestion


@router.get("/documents", response_model=DocumentListResponse)
def list_documents(
    collection_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DocumentListResponse:
    return DocumentListResponse(
        documents=_service.list_documents(
            db,
            workspace_id=user.workspace_id,
            user_id=user.id,
            user_role=user.role,
            collection_id=collection_id,
        )
    )


@router.post("/documents/{document_id}/reingest", response_model=IngestionResponse)
def reingest_document(
    document_id: str,
    payload: DocumentCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> IngestionResponse:
    return _service.reingest_document(
        db,
        workspace_id=user.workspace_id,
        user_id=user.id,
        user_role=user.role,
        document_id=document_id,
        content=payload.content,
    )


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_document(
    document_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    _service.archive_document(
        db,
        workspace_id=user.workspace_id,
        user_id=user.id,
        user_role=user.role,
        document_id=document_id,
    )


@router.post("/search", response_model=KnowledgeSearchResponse)
def search_knowledge(
    payload: KnowledgeSearchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> KnowledgeSearchResponse:
    """Search the workspace's own sales knowledge.

    Visibility is resolved from the authenticated user, never from the
    request body: there is no parameter here that lets a caller widen its own
    scope.
    """
    return _service.search(
        db,
        workspace_id=user.workspace_id,
        query=payload.query,
        user_id=user.id,
        user_role=user.role,
        collection_types=list(payload.collection_types) if payload.collection_types else None,
        industry=payload.industry,
        limit=payload.limit,
    )


__all__ = ["router"]
