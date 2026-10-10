from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.orm import Session, sessionmaker
from test_agent_runtime import _build_session_factory
from test_knowledge_rag import _collection, _document, _seed_workspace

from app.core.config import clear_settings_cache, get_settings
from app.core.errors import ApiError
from app.modules.knowledge.constants import SERVICES
from app.modules.knowledge.embeddings import EmbeddingResult, EmbeddingRouter
from app.modules.knowledge.models import KnowledgeChunk, KnowledgeDocument
from app.modules.knowledge.retrieval import KnowledgeRetriever
from app.modules.knowledge.service import KnowledgeService
from app.modules.users.models import User, Workspace

# --- Knowledge-layer security evals --------------------------------------
#
# The RAG evals next door test whether retrieval returns the *right* answer.
# These test whether it can be made to return an answer it must never
# return, and what happens when the machinery underneath fails.
#
# The distinction that matters throughout: a filter applied inside the SQL
# query is a boundary; a filter applied to rows already in Python is a
# formatting step that a later refactor can drop without any test noticing.


@pytest.fixture(autouse=True)
def _local_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    clear_settings_cache()


def _compiled(**kwargs: Any) -> str:
    retriever = KnowledgeRetriever()
    stmt = retriever._candidate_query(  # noqa: SLF001 - asserting on the boundary itself
        workspace_id=kwargs.pop("workspace_id", 7),
        user_id=kwargs.pop("user_id", None),
        user_role=kwargs.pop("user_role", None),
        document_types=kwargs.pop("document_types", None),
        industry=kwargs.pop("industry", None),
        limit=kwargs.pop("limit", 50),
    )
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))


# --- the filters are in the query, not in Python -------------------------


def test_tenancy_is_constrained_inside_the_sql_not_after_it() -> None:
    sql = _compiled(workspace_id=7)
    # Every joined table carries its own tenancy predicate, so a future join
    # that widens the row set cannot inherit another tenant's rows through a
    # foreign key.
    assert sql.count("workspace_id = 7") >= 3
    assert "LIMIT 50" in sql


def test_visibility_is_constrained_inside_the_sql_not_after_it() -> None:
    # A member with no elevated role: restricted documents must be excluded
    # by the query, never retrieved and then hidden.
    member = _compiled(user_id=42, user_role="sales_user")
    assert "'restricted'" not in member
    assert "'workspace'" in member
    assert "created_by_user_id = 42" in member

    # And a private document is scoped to its author, not merely to the
    # workspace.
    other = _compiled(user_id=43, user_role="sales_user")
    assert "created_by_user_id = 43" in other


def test_an_elevated_role_widens_visibility_only_to_restricted() -> None:
    admin = _compiled(user_id=1, user_role="admin")
    assert "'restricted'" in admin
    # Still tenant-scoped: elevation is about visibility, never about tenancy.
    assert admin.count("workspace_id = 7") >= 3


def test_caller_supplied_metadata_filters_can_only_narrow() -> None:
    """A document_type/industry filter is a narrowing clause, never a bypass.

    These values reach the query from request input (and, through the agent
    tool, ultimately from a model). They must be able to subtract rows and
    nothing else.
    """
    narrowed = _compiled(document_types=("services",), industry="dental")
    assert narrowed.count("workspace_id = 7") >= 3
    assert "document_type IN ('services')" in narrowed
    assert "industry = 'dental'" in narrowed

    # An empty filter tuple does not become "match anything unfiltered".
    unfiltered = _compiled(document_types=())
    assert unfiltered.count("workspace_id = 7") >= 3
    assert "is_active" in unfiltered and "is_current" in unfiltered


def test_archived_and_superseded_rows_are_excluded_by_the_query() -> None:
    sql = _compiled()
    assert "archived_at IS NULL" in sql
    assert "is_active" in sql
    assert "is_current" in sql


# --- ingestion input limits ----------------------------------------------


def _prepare(db: Session) -> tuple[KnowledgeService, Workspace, User, str]:
    service = KnowledgeService()
    workspace, user = _seed_workspace(db, name="Sec", email="sec@example.com")
    collection_id = _collection(
        service, db, workspace_id=workspace.id, slug="services", kind=SERVICES
    )
    return service, workspace, user, collection_id


def test_an_oversized_document_is_rejected_before_anything_is_embedded() -> None:
    session_factory: sessionmaker[Session] = _build_session_factory()
    with session_factory() as db:
        service, workspace, user, collection_id = _prepare(db)
        limit = get_settings().knowledge_max_document_chars
        with pytest.raises(ApiError) as excinfo:
            _document(
                service,
                db,
                workspace_id=workspace.id,
                user_id=user.id,
                collection_id=collection_id,
                title="Huge",
                content="## Section\n\n" + ("word " * limit),
            )
        assert "maximum indexable size" in str(excinfo.value)
        # Nothing was embedded and nothing became retrievable: the limit is
        # enforced before the expensive, chargeable part of the pipeline.
        assert db.query(KnowledgeChunk).count() == 0


def test_content_that_is_not_readable_text_is_rejected_rather_than_indexed() -> None:
    """There is no file-upload surface; documents arrive as text.

    So the question is not "which file types are allowed" but what happens
    when the text is not really text -- binary or control bytes pasted in.
    Such content must be refused, not stored as chunks that later surface as
    an unreadable citation in front of a customer.
    """
    session_factory: sessionmaker[Session] = _build_session_factory()
    with session_factory() as db:
        service, workspace, user, collection_id = _prepare(db)
        with pytest.raises(ApiError):
            _document(
                service,
                db,
                workspace_id=workspace.id,
                user_id=user.id,
                collection_id=collection_id,
                title="Binary",
                content="\x00\x01\x02\x03\x0b\x0c\x7f",
            )
        assert db.query(KnowledgeChunk).count() == 0


# --- embedding provider failure ------------------------------------------


def _broken_embed(self: Any, texts: list[str]) -> EmbeddingResult:
    """A provider that is reachable but always fails.

    Patched onto the router rather than onto one instance, so every caller
    in the pipeline sees the same outage.
    """
    return EmbeddingResult(
        vectors=[],
        provider="broken",
        model="broken",
        dim=0,
        tokens=0,
        latency_ms=1,
        error="provider exploded",
    )


def test_embedding_failure_during_ingestion_leaves_no_partial_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory: sessionmaker[Session] = _build_session_factory()
    with session_factory() as db:
        service, workspace, user, collection_id = _prepare(db)
        # Patch the router itself, so every caller in the pipeline sees
        # the same outage rather than only the one we happened to reach for.
        monkeypatch.setattr(EmbeddingRouter, "embed", _broken_embed)
        with pytest.raises(ApiError):
            _document(
                service,
                db,
                workspace_id=workspace.id,
                user_id=user.id,
                collection_id=collection_id,
                title="Will fail",
                content="## Services\n\nWe build online booking systems for clinics.",
            )
        # A half-embedded document is worse than no document: it retrieves
        # on keywords while silently missing most of its own content.
        assert db.query(KnowledgeChunk).count() == 0
        documents = db.query(KnowledgeDocument).all()
        assert all(document.status != "ready" for document in documents)


def test_embedding_failure_at_search_time_degrades_instead_of_crashing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory: sessionmaker[Session] = _build_session_factory()
    with session_factory() as db:
        service, workspace, user, collection_id = _prepare(db)
        _document(
            service,
            db,
            workspace_id=workspace.id,
            user_id=user.id,
            collection_id=collection_id,
            title="Online Booking",
            content=(
                "## Online booking\n\n"
                "We install an online booking and appointment scheduling system "
                "for clinics, including automated reminders."
            ),
        )
        db.commit()

        monkeypatch.setattr(EmbeddingRouter, "embed", _broken_embed)
        retriever = KnowledgeRetriever()
        outcome = retriever.search(
            db,
            workspace_id=workspace.id,
            query="online booking appointment scheduling",
            user_id=user.id,
            user_role="admin",
        )

        # Keyword matching still works, so a provider outage degrades recall
        # rather than taking the feature down -- and the response says which
        # embedding model was used, which is None here.
        assert outcome.embedding_model is None
        assert outcome.results
        assert all(result.document_title == "Online Booking" for result in outcome.results)


def test_a_failed_query_embedding_never_widens_the_candidate_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Degrading to keyword-only must not degrade the tenancy boundary."""
    session_factory: sessionmaker[Session] = _build_session_factory()
    with session_factory() as db:
        service_a = KnowledgeService()
        workspace_a, user_a = _seed_workspace(db, name="A", email="a@example.com")
        workspace_b, user_b = _seed_workspace(db, name="B", email="b@example.com")
        collection_b = _collection(
            service_a, db, workspace_id=workspace_b.id, slug="services", kind=SERVICES
        )
        _document(
            service_a,
            db,
            workspace_id=workspace_b.id,
            user_id=user_b.id,
            collection_id=collection_b,
            title="Confidential Pricing",
            content="## Pricing\n\nOur retainer floor is 4500 per month for booking work.",
        )
        db.commit()

        monkeypatch.setattr(EmbeddingRouter, "embed", _broken_embed)
        retriever = KnowledgeRetriever()
        outcome = retriever.search(
            db,
            workspace_id=workspace_a.id,
            query="retainer floor pricing booking",
            user_id=user_a.id,
            user_role="admin",
        )
        assert outcome.candidate_count == 0
        assert outcome.results == []
