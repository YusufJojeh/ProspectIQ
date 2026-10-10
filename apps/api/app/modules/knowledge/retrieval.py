from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.modules.knowledge.constants import RETRIEVABLE_STATUSES
from app.modules.knowledge.embeddings import EmbeddingRouter, cosine_similarity
from app.modules.knowledge.models import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDocumentVersion,
)
from app.modules.knowledge.visibility import visibility_clause

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]{2,}")

#: Words that appear in almost every sales document and would otherwise
#: dominate the keyword half of the hybrid score.
_STOPWORDS = frozenset(
    {
        "about", "all", "and", "any", "are", "but", "can", "did", "does", "for",
        "from", "get", "has", "have", "her", "him", "his", "how", "into", "its",
        "not", "one", "our", "out", "should", "than", "that", "the", "their",
        "them", "then", "there", "these", "they", "this", "was", "were", "what",
        "when", "where", "which", "who", "why", "will", "with", "would", "you",
        "your",
        # Two-letter function words. The tokenizer keeps 2+ character tokens
        # (so "ai", "seo" and "sms" survive), which means these have to be
        # listed explicitly: without them an off-topic query such as "how to
        # change the oil in a truck" matches any document containing "to"/"in".
        "an", "as", "at", "be", "by", "do", "he", "if", "in", "is", "it", "me",
        "my", "no", "of", "on", "or", "so", "to", "up", "us", "we",
    }
)


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    """One scored passage, with everything a citation needs."""

    chunk_id: str
    document_id: str
    document_title: str
    document_type: str
    section: str | None
    version: int
    content: str
    score: float
    vector_score: float
    keyword_score: float


@dataclass(frozen=True, slots=True)
class RetrievalOutcome:
    results: list[RetrievedChunk]
    candidate_count: int
    embedding_model: str | None
    #: True when the query had to be embedded by a fallback provider, so the
    #: caller can say "results may be weaker" rather than silently degrading.
    degraded: bool = False


@dataclass
class KnowledgeRetriever:
    """Hybrid (vector + keyword) retrieval over the sales knowledge store.

    Two properties of this implementation matter more than its ranking:

    1. **Tenancy is enforced in the query, never afterwards.** The candidate
       SELECT filters on workspace, document status, current version and
       visibility. A chunk belonging to another workspace, to an archived or
       still-ingesting document, to a superseded version, or to a document
       the caller may not see is never loaded into the process -- so no
       later bug in the Python scoring can leak it.

    2. **Similarity is computed in Python on purpose.** The deployment
       database is MariaDB/MySQL, which has no vector type or index. Rather
       than pretend otherwise, the SQL narrows the candidate set as far as
       the relational predicates allow and cosine similarity runs over that
       bounded set (capped by knowledge_search_candidate_limit). This is a
       real limit: on a very large corpus, recall is bounded by which
       candidates the SQL ordering surfaces. It is documented rather than
       hidden.
    """

    settings: Settings = field(default_factory=get_settings)
    embeddings: EmbeddingRouter = field(default_factory=EmbeddingRouter)

    # --- candidate selection -------------------------------------------

    def _candidate_query(
        self,
        *,
        workspace_id: int,
        user_id: int | None,
        user_role: str | None,
        document_types: tuple[str, ...] | None,
        industry: str | None,
        limit: int,
    ) -> Select[tuple[KnowledgeChunk, KnowledgeDocument, KnowledgeDocumentVersion]]:
        stmt = (
            select(KnowledgeChunk, KnowledgeDocument, KnowledgeDocumentVersion)
            .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
            .join(
                KnowledgeDocumentVersion,
                KnowledgeDocumentVersion.id == KnowledgeChunk.document_version_id,
            )
            .where(
                # Tenancy, asserted on every table in the join rather than
                # inferred from the foreign keys.
                KnowledgeChunk.workspace_id == workspace_id,
                KnowledgeDocument.workspace_id == workspace_id,
                KnowledgeDocumentVersion.workspace_id == workspace_id,
                KnowledgeChunk.is_active.is_(True),
                KnowledgeDocumentVersion.is_current.is_(True),
                KnowledgeDocument.status.in_(tuple(RETRIEVABLE_STATUSES)),
                KnowledgeDocument.archived_at.is_(None),
                visibility_clause(user_id=user_id, user_role=user_role),
            )
        )
        if document_types:
            stmt = stmt.where(KnowledgeDocument.document_type.in_(document_types))
        if industry:
            stmt = stmt.where(KnowledgeDocument.industry == industry)
        return stmt.order_by(KnowledgeChunk.id.desc()).limit(limit)

    # --- scoring --------------------------------------------------------

    def _keyword_scores(self, query: str, contents: list[str]) -> list[float]:
        """A small IDF-weighted overlap score.

        This is the half of the hybrid that catches exact product names,
        pricing terms and client names -- the things an embedding blurs and a
        salesperson cannot afford to have blurred.
        """
        query_terms = {
            term for term in _TOKEN_RE.findall(query.lower()) if term not in _STOPWORDS
        }
        if not query_terms or not contents:
            return [0.0] * len(contents)

        tokenized = [set(_TOKEN_RE.findall(content.lower())) for content in contents]
        total_docs = len(tokenized)
        scores: list[float] = []
        idf: dict[str, float] = {}
        for term in query_terms:
            document_frequency = sum(1 for tokens in tokenized if term in tokens)
            idf[term] = math.log(1.0 + (total_docs / (1.0 + document_frequency)))

        max_possible = sum(idf.values()) or 1.0
        for tokens in tokenized:
            matched = sum(idf[term] for term in query_terms if term in tokens)
            scores.append(matched / max_possible)
        return scores

    def search(
        self,
        db: Session,
        *,
        workspace_id: int,
        query: str,
        user_id: int | None = None,
        user_role: str | None = None,
        document_types: tuple[str, ...] | None = None,
        industry: str | None = None,
        limit: int | None = None,
    ) -> RetrievalOutcome:
        cleaned = query.strip()
        if not cleaned:
            return RetrievalOutcome(results=[], candidate_count=0, embedding_model=None)

        top_k = min(
            limit or self.settings.knowledge_search_default_limit,
            self.settings.knowledge_search_max_limit,
        )
        rows = list(
            db.execute(
                self._candidate_query(
                    workspace_id=workspace_id,
                    user_id=user_id,
                    user_role=user_role,
                    document_types=document_types,
                    industry=industry,
                    limit=self.settings.knowledge_search_candidate_limit,
                )
            ).all()
        )
        if not rows:
            return RetrievalOutcome(results=[], candidate_count=0, embedding_model=None)

        embedded = self.embeddings.embed([cleaned])
        query_vector = embedded.vectors[0] if embedded.ok else []
        query_model = embedded.model if embedded.ok else None

        contents = [row[0].content for row in rows]
        keyword_scores = self._keyword_scores(cleaned, contents)
        vector_weight = self.settings.knowledge_hybrid_vector_weight if query_vector else 0.0

        scored: list[RetrievedChunk] = []
        for (chunk, document, version), keyword_score in zip(rows, keyword_scores, strict=True):
            vector_score = 0.0
            # A chunk embedded by a different model lives in a different
            # vector space; comparing the two would produce a confident
            # nonsense number. Such a chunk can still be retrieved on its
            # keyword score alone.
            if query_vector and chunk.embedding_json and chunk.embedding_model == query_model:
                vector_score = cosine_similarity(
                    query_vector,
                    chunk.embedding_json,
                    right_norm=chunk.embedding_norm,
                )
            combined = vector_weight * vector_score + (1.0 - vector_weight) * keyword_score
            if combined < self.settings.knowledge_min_similarity:
                continue
            if (
                keyword_score == 0.0
                and vector_score < self.settings.knowledge_min_vector_only_similarity
            ):
                continue
            scored.append(
                RetrievedChunk(
                    chunk_id=chunk.public_id,
                    document_id=document.public_id,
                    document_title=document.title,
                    document_type=document.document_type,
                    section=chunk.section,
                    version=version.version,
                    content=chunk.content,
                    score=round(combined, 6),
                    vector_score=round(vector_score, 6),
                    keyword_score=round(keyword_score, 6),
                )
            )

        scored.sort(key=lambda item: (item.score, item.chunk_id), reverse=True)
        return RetrievalOutcome(
            results=scored[:top_k],
            candidate_count=len(rows),
            embedding_model=query_model,
            degraded=embedded.fallback_used or not embedded.ok,
        )


def excerpt(content: str, *, max_chars: int) -> str:
    """Trim a chunk to a citation-sized excerpt on a word boundary."""
    text = content.strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    boundary = cut.rfind(" ")
    if boundary > max_chars // 2:
        cut = cut[:boundary]
    return f"{cut.rstrip()}..."


__all__ = ["KnowledgeRetriever", "RetrievalOutcome", "RetrievedChunk", "excerpt"]
