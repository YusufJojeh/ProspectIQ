from __future__ import annotations

import hashlib
import logging
import math
import re
import time
from dataclasses import dataclass, field
from typing import Protocol

import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

#: Dimension of the deterministic local embedding. Small enough to keep
#: JSON rows compact, large enough that unrelated documents do not collide.
LOCAL_EMBEDDING_DIM = 256
LOCAL_EMBEDDING_MODEL = "local-hashing-v1"

_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True, slots=True)
class EmbeddingResult:
    """One embedding batch, with everything the usage ledger needs.

    The model is never chosen by a user or by the agent: it comes from
    settings, because a per-request model would let two documents in the
    same collection land in incompatible vector spaces.
    """

    vectors: list[list[float]]
    provider: str
    model: str
    dim: int
    tokens: int
    latency_ms: int
    fallback_used: bool = False
    error: str | None = None
    trace_id: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.vectors)


class EmbeddingProvider(Protocol):
    name: str
    model: str
    dim: int

    def embed(self, texts: list[str]) -> EmbeddingResult: ...


def _approx_tokens(text: str) -> int:
    """A deliberately cheap token estimate.

    Exact provider tokenization is not worth a dependency here: this number
    drives cost *estimates* and budget counters, and every real provider
    response overwrites it with the usage it reports.
    """
    return max(1, len(text) // 4)


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class LocalHashingEmbeddingProvider:
    """A deterministic, dependency-free embedding used when no embedding
    API is configured, and in tests.

    It is a hashed bag-of-words projection with sublinear term weighting:
    documents that share vocabulary land near each other, documents that do
    not stay apart. That is genuinely useful for retrieval over a
    workspace's own service catalogue and case studies, and it makes the
    RAG evals deterministic and offline.

    It is NOT a semantic model: it cannot match "appointment scheduling"
    to "booking system" unless the words overlap. Deployments that need
    true semantic recall configure a real embedding provider; this one
    guarantees the pipeline is always functional rather than silently
    disabled.
    """

    name = "local"

    def __init__(self, dim: int = LOCAL_EMBEDDING_DIM) -> None:
        self.dim = dim
        self.model = LOCAL_EMBEDDING_MODEL

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        tokens = _tokenize(text)
        if not tokens:
            return vector
        counts: dict[str, int] = {}
        for token in tokens:
            counts[token] = counts.get(token, 0) + 1
        for token, count in counts.items():
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self.dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            # Sublinear weighting: a term repeated ten times is not ten
            # times as important as one mentioned once.
            vector[index] += sign * (1.0 + math.log(count))
        norm = math.sqrt(sum(value * value for value in vector))
        if norm > 0:
            vector = [value / norm for value in vector]
        return vector

    def embed(self, texts: list[str]) -> EmbeddingResult:
        started = time.monotonic()
        vectors = [self._embed_one(text) for text in texts]
        return EmbeddingResult(
            vectors=vectors,
            provider=self.name,
            model=self.model,
            dim=self.dim,
            tokens=sum(_approx_tokens(text) for text in texts),
            latency_ms=int((time.monotonic() - started) * 1000),
        )


class OpenAIEmbeddingProvider:
    """Embeddings via the OpenAI-compatible /embeddings endpoint.

    Uses the same base URL and key as the rest of the OpenAI integration.
    The model comes from settings and is never user- or model-controlled.
    """

    name = "openai"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.model = settings.embedding_model
        self.dim = settings.embedding_dim

    def embed(self, texts: list[str]) -> EmbeddingResult:
        started = time.monotonic()
        try:
            with httpx.Client(
                timeout=httpx.Timeout(self._settings.embedding_timeout_seconds, connect=10.0),
                headers={
                    "Authorization": f"Bearer {self._settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
            ) as client:
                response = client.post(
                    f"{self._settings.openai_base_url.rstrip('/')}/embeddings",
                    json={"model": self.model, "input": texts},
                )
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:  # noqa: BLE001 - provider failure is expected and handled
            logger.warning("knowledge.embedding.failed provider=openai error=%s", exc)
            return EmbeddingResult(
                vectors=[],
                provider=self.name,
                model=self.model,
                dim=self.dim,
                tokens=0,
                latency_ms=int((time.monotonic() - started) * 1000),
                error=str(exc),
            )

        ordered = sorted(payload.get("data", []), key=lambda item: item.get("index", 0))
        vectors = [[float(value) for value in item["embedding"]] for item in ordered]
        usage = payload.get("usage") or {}
        dim = len(vectors[0]) if vectors else self.dim
        return EmbeddingResult(
            vectors=vectors,
            provider=self.name,
            model=self.model,
            dim=dim,
            tokens=int(usage.get("total_tokens") or sum(_approx_tokens(t) for t in texts)),
            latency_ms=int((time.monotonic() - started) * 1000),
        )


@dataclass
class EmbeddingRouter:
    """Chooses the embedding provider and applies the fallback policy.

    Fallback here is only ever *semantically safe* in one direction: if the
    remote provider fails, the local provider can still index or query, and
    every affected row records which model produced it. What the router will
    never do is silently mix vector spaces at query time -- retrieval
    compares a query vector only against chunks embedded with the same
    model (see retrieval.py), so a fallback degrades recall visibly rather
    than returning quietly wrong neighbours.
    """

    settings: Settings = field(default_factory=get_settings)

    def primary(self) -> EmbeddingProvider:
        if self.settings.embedding_provider == "local":
            return LocalHashingEmbeddingProvider()
        if self.settings.embedding_provider == "openai" and self.settings.has_openai_configured:
            return OpenAIEmbeddingProvider(self.settings)
        # "auto"
        if self.settings.has_openai_configured and not self.settings.is_testing:
            return OpenAIEmbeddingProvider(self.settings)
        return LocalHashingEmbeddingProvider()

    def embed(self, texts: list[str]) -> EmbeddingResult:
        if not texts:
            return EmbeddingResult(
                vectors=[], provider="none", model="none", dim=0, tokens=0, latency_ms=0
            )
        provider = self.primary()
        result = provider.embed(texts)
        if result.ok:
            return result
        if not self.settings.embedding_fallback_enabled or provider.name == "local":
            return result
        logger.warning(
            "knowledge.embedding.fallback from=%s reason=%s", provider.name, result.error
        )
        fallback = LocalHashingEmbeddingProvider().embed(texts)
        return EmbeddingResult(
            vectors=fallback.vectors,
            provider=fallback.provider,
            model=fallback.model,
            dim=fallback.dim,
            tokens=fallback.tokens,
            latency_ms=result.latency_ms + fallback.latency_ms,
            fallback_used=True,
        )


def cosine_similarity(left: list[float], right: list[float], *, right_norm: float = 0.0) -> float:
    """Cosine similarity, using a precomputed norm for the stored side.

    Returns 0.0 for mismatched dimensions rather than raising: a chunk
    embedded with a different model must simply not match, never crash a
    search.
    """
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    norm = right_norm or math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or norm == 0.0:
        return 0.0
    return dot / (left_norm * norm)


def vector_norm(vector: list[float]) -> float:
    return math.sqrt(sum(value * value for value in vector))


__all__ = [
    "LOCAL_EMBEDDING_DIM",
    "LOCAL_EMBEDDING_MODEL",
    "EmbeddingProvider",
    "EmbeddingResult",
    "EmbeddingRouter",
    "LocalHashingEmbeddingProvider",
    "OpenAIEmbeddingProvider",
    "cosine_similarity",
    "vector_norm",
]
