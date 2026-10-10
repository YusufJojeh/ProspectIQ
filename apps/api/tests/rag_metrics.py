"""Retrieval metric computation shared by the eval test and the report script."""

from __future__ import annotations

import math
import statistics
import time
from dataclasses import dataclass, field
from typing import Any

from rag_golden_dataset import DOCS, QUERIES, GoldenQuery
from sqlalchemy.orm import Session
from test_knowledge_rag import _collection, _document

from app.modules.knowledge.retrieval import KnowledgeRetriever
from app.modules.knowledge.service import KnowledgeService

MODES: dict[str, float] = {"hybrid": -1.0, "vector": 1.0, "keyword": 0.0}
#: Chunks requested per query; documents are de-duplicated afterwards, so this
#: only needs to be large enough to fill a top-5 of distinct documents.
FETCH_LIMIT = 15


def seed_golden_corpus(db: Session, *, workspace_id: int, user_id: int) -> dict[str, str]:
    """Ingest the golden corpus; returns {title: document public id}."""
    service = KnowledgeService()
    collections: dict[str, str] = {}
    ids: dict[str, str] = {}
    for doc in DOCS:
        if doc.kind not in collections:
            collections[doc.kind] = _collection(
                service, db, workspace_id=workspace_id, slug=f"g-{doc.kind}", kind=doc.kind
            )
        ids[doc.title] = _document(
            service,
            db,
            workspace_id=workspace_id,
            user_id=user_id,
            collection_id=collections[doc.kind],
            title=doc.title,
            content=doc.content,
        )
    return ids


@dataclass
class ModeReport:
    mode: str
    recall_at: dict[int, float] = field(default_factory=dict)
    hit_at: dict[int, float] = field(default_factory=dict)
    precision_at_3: float = 0.0
    mrr: float = 0.0
    ndcg_at_5: float = 0.0
    negative_false_positive_rate: float = 0.0
    negative_count: int = 0
    positive_count: int = 0
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    by_bucket_recall_at_3: dict[str, float] = field(default_factory=dict)
    misses_at_5: list[str] = field(default_factory=list)

    def as_row(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "R@1": round(self.recall_at[1], 3),
            "R@3": round(self.recall_at[3], 3),
            "R@5": round(self.recall_at[5], 3),
            "Hit@3": round(self.hit_at[3], 3),
            "P@3": round(self.precision_at_3, 3),
            "MRR": round(self.mrr, 3),
            "nDCG@5": round(self.ndcg_at_5, 3),
            "neg_FP": round(self.negative_false_positive_rate, 3),
            "p50_ms": round(self.latency_p50_ms, 1),
            "p95_ms": round(self.latency_p95_ms, 1),
        }


def _distinct_docs(titles: list[str]) -> list[str]:
    seen: list[str] = []
    for title in titles:
        if title not in seen:
            seen.append(title)
    return seen


def _ndcg(ranked: list[str], relevant: set[str], k: int) -> float:
    gains = [1.0 if title in relevant else 0.0 for title in ranked[:k]]
    dcg = sum(g / math.log2(i + 2) for i, g in enumerate(gains))
    ideal = sum(1.0 / math.log2(i + 2) for i in range(min(k, len(relevant))))
    return dcg / ideal if ideal else 0.0


def _percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, max(0, math.ceil(pct / 100.0 * len(ordered)) - 1))
    return ordered[index]


def evaluate(
    db: Session,
    *,
    workspace_id: int,
    user_id: int,
    mode: str,
    queries: tuple[GoldenQuery, ...] = QUERIES,
    retriever: KnowledgeRetriever | None = None,
) -> ModeReport:
    base = retriever or KnowledgeRetriever()
    weight = MODES[mode]
    if weight >= 0.0:
        base = KnowledgeRetriever(
            settings=base.settings.model_copy(update={"knowledge_hybrid_vector_weight": weight}),
            embeddings=base.embeddings,
        )

    report = ModeReport(mode=mode)
    ks = (1, 3, 5)
    recalls: dict[int, list[float]] = {k: [] for k in ks}
    hits: dict[int, list[float]] = {k: [] for k in ks}
    precisions: list[float] = []
    reciprocal: list[float] = []
    ndcgs: list[float] = []
    latencies: list[float] = []
    bucket_r3: dict[str, list[float]] = {}
    negatives_returning = 0

    for item in queries:
        started = time.perf_counter()
        outcome = base.search(
            db, workspace_id=workspace_id, user_id=user_id, query=item.query, limit=FETCH_LIMIT
        )
        latencies.append((time.perf_counter() - started) * 1000.0)
        ranked = _distinct_docs([chunk.document_title for chunk in outcome.results])

        if not item.relevant:
            report.negative_count += 1
            if ranked:
                negatives_returning += 1
            continue

        report.positive_count += 1
        relevant = set(item.relevant)
        for k in ks:
            found = len(relevant & set(ranked[:k]))
            recalls[k].append(found / len(relevant))
            hits[k].append(1.0 if found else 0.0)
        precisions.append(len(relevant & set(ranked[:3])) / 3.0)
        rank = next((i + 1 for i, t in enumerate(ranked) if t in relevant), None)
        reciprocal.append(1.0 / rank if rank else 0.0)
        ndcgs.append(_ndcg(ranked, relevant, 5))
        bucket_r3.setdefault(item.bucket, []).append(recalls[3][-1])
        if not relevant & set(ranked[:5]):
            report.misses_at_5.append(item.query)

    report.recall_at = {k: statistics.fmean(v) for k, v in recalls.items()}
    report.hit_at = {k: statistics.fmean(v) for k, v in hits.items()}
    report.precision_at_3 = statistics.fmean(precisions)
    report.mrr = statistics.fmean(reciprocal)
    report.ndcg_at_5 = statistics.fmean(ndcgs)
    report.negative_false_positive_rate = (
        negatives_returning / report.negative_count if report.negative_count else 0.0
    )
    report.latency_p50_ms = _percentile(latencies, 50)
    report.latency_p95_ms = _percentile(latencies, 95)
    report.by_bucket_recall_at_3 = {b: statistics.fmean(v) for b, v in bucket_r3.items()}
    return report
