"""RAG retrieval scale benchmark.

Answers one question with measurements: does cosine similarity in Python over
a SQL-narrowed candidate set stay acceptable as the corpus grows, and what
does the candidate cap cost in recall?

    python scripts/rag_scale_benchmark.py --sizes 1000 10000 50000

Method
------
* One workspace, N synthetic chunks (20 per document), inserted with bulk
  Core inserts and real local-hashing embeddings, into a temporary SQLite
  file. SQLite stands in for MariaDB: it exercises the same query shape and
  the same Python scoring, but its SQL timings are indicative, not MariaDB's.
* 40 "target" chunks carry three unique marker tokens. They are scattered
  across the WHOLE insertion range, because the candidate query orders by
  ``chunk.id DESC LIMIT cap`` -- a target inserted early is exactly the case
  the cap can drop.
* Each target has one query built from its markers plus generic words.
  Recall@5 is measured at three caps: the shipped default, the configured
  maximum (5000) and unbounded (cap = corpus size, the ground truth).
* Time is split into candidate retrieval (SQL + row load), query embedding,
  and scoring (keyword + cosine + sort) -- the last is the part a vector
  index would replace.

Nothing here touches a real provider or a real database.
"""

from __future__ import annotations

import argparse
import math
import os
import random
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("EMBEDDING_PROVIDER", "local")

from sqlalchemy import create_engine, insert  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.core.config import clear_settings_cache, get_settings  # noqa: E402
from app.core.database import Base  # noqa: E402
from app.modules.knowledge.embeddings import (  # noqa: E402
    EmbeddingRouter,
    LocalHashingEmbeddingProvider,
    vector_norm,
)
from app.modules.knowledge.models import (  # noqa: E402
    KnowledgeChunk,
    KnowledgeCollection,
    KnowledgeDocument,
    KnowledgeDocumentVersion,
)
from app.modules.knowledge.retrieval import KnowledgeRetriever  # noqa: E402
from app.modules.users.models import Workspace  # noqa: E402

CHUNKS_PER_DOC = 20
TARGETS = 40
GENERIC = (
    "customer booking service clinic reminder review google appointment quote follow "
    "outreach pricing retainer branch owner website phone message report audit growth "
    "campaign local search rating visit staff team offer proposal contract"
).split()


def _p(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, math.ceil(pct / 100 * len(ordered)) - 1))]


def build_corpus(db: Session, size: int, rng: random.Random) -> list[tuple[str, str]]:
    """Insert `size` chunks; return [(query, target_document_title)]."""
    workspace = Workspace(name="Scale")
    db.add(workspace)
    db.flush()
    collection = KnowledgeCollection(
        workspace_id=workspace.id, slug="scale", name="Scale", collection_type="services"
    )
    db.add(collection)
    db.flush()

    doc_count = math.ceil(size / CHUNKS_PER_DOC)
    target_positions = set(rng.sample(range(size), min(TARGETS, size)))
    embedder = LocalHashingEmbeddingProvider()
    vocab = [f"w{rng.randrange(3000)}" for _ in range(3000)] + GENERIC * 20

    queries: list[tuple[str, str]] = []
    chunk_rows: list[dict[str, object]] = []
    position = 0
    for d in range(doc_count):
        title = f"Doc {d}"
        document = KnowledgeDocument(
            workspace_id=workspace.id, collection_id=collection.id,
            document_type="services", title=title, status="ready", current_version=1,
        )
        db.add(document)
        db.flush()
        version = KnowledgeDocumentVersion(
            workspace_id=workspace.id, document_id=document.id, version=1,
            checksum=f"c{d}", content="", is_current=1,
        )
        db.add(version)
        db.flush()
        texts: list[str] = []
        for _ in range(CHUNKS_PER_DOC):
            if position >= size:
                break
            words = [rng.choice(vocab) for _ in range(40)]
            if position in target_positions:
                marker = f"zq{position}a zq{position}b zq{position}c"
                words[5:5] = marker.split()
                generic = " ".join(rng.sample(GENERIC, 3))
                queries.append((f"{marker} {generic}", title))
            texts.append(" ".join(words))
            position += 1
        for c, (text, vector) in enumerate(
            zip(texts, embedder.embed(texts).vectors, strict=True)
        ):
            rounded = [round(v, 5) for v in vector]
            chunk_rows.append(
                {
                    "public_id": f"kchk_{d}_{c}", "workspace_id": workspace.id,
                    "document_id": document.id, "document_version_id": version.id,
                    "chunk_index": c, "content": text, "token_count": len(text) // 4,
                    "embedding_json": rounded, "embedding_model": embedder.model,
                    "embedding_dim": embedder.dim, "embedding_norm": vector_norm(rounded),
                    "is_active": 1, "metadata_json": {},
                }
            )
        if len(chunk_rows) >= 2000:
            db.execute(insert(KnowledgeChunk), chunk_rows)
            chunk_rows = []
    if chunk_rows:
        db.execute(insert(KnowledgeChunk), chunk_rows)
    db.commit()
    return queries


def measure(db: Session, workspace_id: int, cap: int, queries: list[tuple[str, str]]) -> dict[str, float]:
    settings = get_settings().model_copy(update={"knowledge_search_candidate_limit": cap})
    retriever = KnowledgeRetriever(settings=settings, embeddings=EmbeddingRouter())
    candidate_ms: list[float] = []
    embed_ms: list[float] = []
    total_ms: list[float] = []
    hits = 0
    for query, target in queries:
        t0 = time.perf_counter()
        rows = db.execute(
            retriever._candidate_query(  # noqa: SLF001 - benchmark of an internal stage
                workspace_id=workspace_id, user_id=None, user_role=None,
                document_types=None, industry=None, limit=cap,
            )
        ).all()
        candidate_ms.append((time.perf_counter() - t0) * 1000)
        del rows
        t1 = time.perf_counter()
        retriever.embeddings.embed([query])
        embed_ms.append((time.perf_counter() - t1) * 1000)
        t2 = time.perf_counter()
        outcome = retriever.search(db, workspace_id=workspace_id, query=query, limit=20)
        total_ms.append((time.perf_counter() - t2) * 1000)
        titles: list[str] = []
        for chunk in outcome.results:
            if chunk.document_title not in titles:
                titles.append(chunk.document_title)
        hits += 1 if target in titles[:5] else 0
    scoring = [max(0.0, t - c - e) for t, c, e in zip(total_ms, candidate_ms, embed_ms, strict=True)]
    return {
        "recall@5": hits / len(queries),
        "candidates": float(min(cap, db.query(KnowledgeChunk).count())),
        "candidate_ms_p50": statistics.median(candidate_ms),
        "embed_ms_p50": statistics.median(embed_ms),
        "scoring_ms_p50": statistics.median(scoring),
        "total_ms_p50": statistics.median(total_ms),
        "total_ms_p95": _p(total_ms, 95),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", type=int, nargs="+", default=[1000, 10000, 50000])
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    clear_settings_cache()
    default_cap = get_settings().knowledge_search_candidate_limit

    print(f"default candidate cap = {default_cap}; SQLite stand-in for MariaDB; local embeddings")
    header = (
        f"{'chunks':>7} {'cap':>7} {'cands':>6} {'recall@5':>8} "
        f"{'sql p50':>8} {'embed p50':>9} {'score p50':>9} {'total p50':>9} {'total p95':>9}"
    )
    print(header)
    for size in args.sizes:
        rng = random.Random(args.seed)
        with tempfile.TemporaryDirectory() as tmp:
            engine = create_engine(f"sqlite+pysqlite:///{tmp}/scale.db", future=True)
            Base.metadata.create_all(engine)
            factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
            with factory() as db:
                built = time.perf_counter()
                queries = build_corpus(db, size, rng)
                workspace_id = db.query(Workspace).one().id
                print(f"  built {size} chunks in {time.perf_counter() - built:.1f}s")
                for cap in sorted({default_cap, 5000, size}):
                    m = measure(db, workspace_id, cap, queries)
                    print(
                        f"{size:>7} {cap:>7} {int(m['candidates']):>6} {m['recall@5']:>8.3f} "
                        f"{m['candidate_ms_p50']:>8.1f} {m['embed_ms_p50']:>9.2f} "
                        f"{m['scoring_ms_p50']:>9.1f} {m['total_ms_p50']:>9.1f} {m['total_ms_p95']:>9.1f}"
                    )
            engine.dispose()


if __name__ == "__main__":
    main()
