"""The single definition of who may see a knowledge document.

Retrieval, listing and mutation all use this rule so that a document a caller
cannot retrieve is also one they cannot list, re-ingest or archive. It is
applied inside the SQL query (never load-then-filter) and, for single
documents fetched by id, as a predicate.
"""

from __future__ import annotations

from sqlalchemy import ColumnElement, or_

from app.modules.knowledge.constants import (
    RESTRICTED_ROLES,
    VISIBILITY_PRIVATE,
    VISIBILITY_RESTRICTED,
    VISIBILITY_WORKSPACE,
)
from app.modules.knowledge.models import KnowledgeDocument


def visibility_clause(*, user_id: int | None, user_role: str | None) -> ColumnElement[bool]:
    clauses: list[ColumnElement[bool]] = [KnowledgeDocument.visibility == VISIBILITY_WORKSPACE]
    if user_id is not None:
        clauses.append(
            (KnowledgeDocument.visibility == VISIBILITY_PRIVATE)
            & (KnowledgeDocument.created_by_user_id == user_id)
        )
    if user_role is not None and user_role in RESTRICTED_ROLES:
        clauses.append(KnowledgeDocument.visibility == VISIBILITY_RESTRICTED)
    return or_(*clauses)


def can_view(document: KnowledgeDocument, *, user_id: int | None, user_role: str | None) -> bool:
    """Python mirror of `visibility_clause` for a document already loaded by id."""
    if document.visibility == VISIBILITY_WORKSPACE:
        return True
    if document.visibility == VISIBILITY_PRIVATE:
        return user_id is not None and document.created_by_user_id == user_id
    if document.visibility == VISIBILITY_RESTRICTED:
        return user_role is not None and user_role in RESTRICTED_ROLES
    return False
