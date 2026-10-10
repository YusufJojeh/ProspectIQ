from __future__ import annotations

from typing import Any

import pytest
from rag_golden_dataset import DOCS, QUERIES
from rag_metrics import MODES, ModeReport, evaluate, seed_golden_corpus
from sqlalchemy.orm import Session, sessionmaker
from test_agent_runtime import _build_session_factory
from test_knowledge_rag import _seed_workspace

from app.core.config import clear_settings_cache
from app.modules.knowledge.constants import CASE_STUDIES
from app.modules.knowledge.retrieval import KnowledgeRetriever
from app.modules.knowledge.service import KnowledgeService

# --- Retrieval quality: golden-dataset metrics --------------------------------
#
# Run with `pytest tests/test_rag_retrieval_metrics.py -s` to print the table.


@pytest.fixture(autouse=True)
def _local_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    clear_settings_cache()


def _reports() -> dict[str, ModeReport]:
    factory: sessionmaker[Session] = _build_session_factory()
    with factory() as db:
        workspace, user = _seed_workspace(db, name="Golden", email="golden@example.com")
        seed_golden_corpus(db, workspace_id=workspace.id, user_id=user.id)
        return {
            mode: evaluate(db, workspace_id=workspace.id, user_id=user.id, mode=mode)
            for mode in MODES
        }


def test_golden_dataset_shape() -> None:
    assert len(DOCS) >= 30
    assert 30 <= len(QUERIES) <= 100
    negatives = [q for q in QUERIES if not q.relevant]
    assert len(negatives) >= 5


def test_report_retrieval_baseline(capsys: pytest.CaptureFixture[str]) -> None:
    reports = _reports()
    with capsys.disabled():
        print("\n=== RAG retrieval baseline (local hashing embeddings) ===")
        print(
            f"docs={len(DOCS)} queries={len(QUERIES)} "
            f"positive={reports['hybrid'].positive_count} negative={reports['hybrid'].negative_count}"
        )
        for report in reports.values():
            print(report.as_row())
        for report in reports.values():
            print(report.mode, "R@3 by bucket:", {k: round(v, 3) for k, v in report.by_bucket_recall_at_3.items()})
        print("hybrid misses@5:", reports["hybrid"].misses_at_5)


# --- Regression thresholds ----------------------------------------------------
#
# Set from the OBSERVED baseline above (hybrid, local hashing embeddings,
# 31 docs / 46 positive / 10 negative queries), each with a margin so ordinary
# ranking jitter does not trip them but a real regression does:
#
#   metric               observed   floor
#   Recall@3             0.826      0.75
#   Recall@5             0.848      0.78
#   MRR                  0.842      0.75
#   lexical Recall@3     1.000      0.95
#   negative FP rate     0.200      <= 0.30
#   p95 latency          ~6 ms      < 250 ms (only catches an order-of-magnitude blow-up)
#
# The semantic bucket (Recall@3 ~0.33) is deliberately NOT gated: the local
# hashing embedder is lexical, so that number measures the embedder, not the
# retriever. Gate it when a real embedding model is the default.


def test_hybrid_meets_baseline_regression_floors() -> None:
    hybrid = _reports()["hybrid"]
    assert hybrid.recall_at[3] >= 0.75, hybrid.as_row()
    assert hybrid.recall_at[5] >= 0.78, hybrid.as_row()
    assert hybrid.mrr >= 0.75, hybrid.as_row()
    assert hybrid.by_bucket_recall_at_3["lexical"] >= 0.95, hybrid.as_row()
    assert hybrid.negative_false_positive_rate <= 0.30, hybrid.as_row()
    assert hybrid.latency_p95_ms < 250, hybrid.as_row()


def test_hybrid_is_not_worse_than_vector_only_on_ranking() -> None:
    reports = _reports()
    assert reports["hybrid"].mrr >= reports["vector"].mrr
    assert reports["hybrid"].recall_at[1] >= reports["vector"].recall_at[1]


def test_function_words_alone_never_retrieve_anything() -> None:
    """Regression for the defect the first baseline exposed (neg FP 50%)."""
    factory: sessionmaker[Session] = _build_session_factory()
    with factory() as db:
        workspace, user = _seed_workspace(db, name="Golden", email="golden@example.com")
        seed_golden_corpus(db, workspace_id=workspace.id, user_id=user.id)
        retriever = KnowledgeRetriever()
        for query in ("how to change the oil in a diesel truck", "who won the football world cup"):
            outcome = retriever.search(db, workspace_id=workspace.id, user_id=user.id, query=query)
            assert outcome.results == [], (query, [c.document_title for c in outcome.results])


# --- Filters / isolation / visibility / deletion on the golden corpus --------


def test_golden_corpus_filters_isolation_visibility_and_deletion() -> None:
    factory: sessionmaker[Session] = _build_session_factory()
    service = KnowledgeService()
    retriever = KnowledgeRetriever()
    query = "what is the starting retainer price per month in SAR"
    with factory() as db:
        workspace, user = _seed_workspace(db, name="Golden", email="golden@example.com")
        other, other_user = _seed_workspace(db, name="Other", email="other@example.com")
        ids = seed_golden_corpus(db, workspace_id=workspace.id, user_id=user.id)

        def titles(**kwargs: Any) -> list[str]:
            params: dict[str, Any] = {"workspace_id": workspace.id, "user_id": user.id, "query": query}
            params.update(kwargs)
            return [c.document_title for c in retriever.search(db, **params).results]

        assert titles()[0] == "Retainer Pricing Guidance"

        # type filter: only the requested document type may come back
        only_cases = retriever.search(
            db, workspace_id=workspace.id, user_id=user.id, query=query,
            document_types=(CASE_STUDIES,),
        ).results
        assert all(c.document_type == CASE_STUDIES for c in only_cases)
        assert "Retainer Pricing Guidance" not in titles(document_types=(CASE_STUDIES,))

        # tenant isolation: another workspace sees nothing of ours
        assert (
            retriever.search(db, workspace_id=other.id, user_id=other_user.id, query=query).results
            == []
        )

        # deletion: an archived document leaves the ranking immediately
        service.archive_document(
            db,
            workspace_id=workspace.id,
            user_id=user.id,
            user_role="admin",
            document_id=ids["Retainer Pricing Guidance"],
        )
        db.commit()
        assert "Retainer Pricing Guidance" not in titles()
