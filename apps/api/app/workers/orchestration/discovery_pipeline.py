from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from app.modules.provider_serpapi.schemas import LeadCandidate

DiscoveryMode = Literal["single_path", "multi_query_single_engine", "multi_engine_multi_query"]

_ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s\u0600-\u06FF]", re.UNICODE)

_EN_TO_AR_KEYWORDS: dict[str, str] = {
    "beauty salon": "\u0635\u0627\u0644\u0648\u0646 \u062a\u062c\u0645\u064a\u0644",
    "cafe": "\u0645\u0642\u0647\u0649",
    "clinic": "\u0639\u064a\u0627\u062f\u0629",
    "construction": "\u0625\u0646\u0634\u0627\u0621",
    "dental clinic": "\u0639\u064a\u0627\u062f\u0629 \u0623\u0633\u0646\u0627\u0646",
    "dentist": "\u0637\u0628\u064a\u0628 \u0623\u0633\u0646\u0627\u0646",
    "dermatology clinic": "\u0639\u064a\u0627\u062f\u0629 \u062c\u0644\u062f\u064a\u0629",
    "development": "\u062a\u0637\u0648\u064a\u0631",
    "digital marketing agency": "\u0634\u0631\u0643\u0629 \u062a\u0633\u0648\u064a\u0642 \u0631\u0642\u0645\u064a",
    "financing": "\u062a\u0645\u0648\u064a\u0644",
    "gym": "\u0646\u0627\u062f\u064a \u0631\u064a\u0627\u0636\u064a",
    "language school": "\u0645\u0631\u0643\u0632 \u062a\u0639\u0644\u064a\u0645 \u0644\u063a\u0627\u062a",
    "law firm": "\u0645\u0643\u062a\u0628 \u0645\u062d\u0627\u0645\u0627\u0629",
    "real estate": "\u0627\u0644\u0639\u0642\u0627\u0631\u0627\u062a",
    "restaurant": "\u0645\u0637\u0639\u0645",
    "veterinary clinic": "\u0639\u064a\u0627\u062f\u0629 \u0628\u064a\u0637\u0631\u064a\u0629",
}
_AR_TO_EN_KEYWORDS: dict[str, str] = {
    "\u0627\u0644\u062a\u0637\u0648\u064a\u0631 \u0627\u0644\u0639\u0642\u0627\u0631\u064a": "real estate development",
    "\u0627\u0644\u0639\u0642\u0627\u0631\u0627\u062a": "real estate",
    "\u062a\u0637\u0648\u064a\u0631": "development",
    "\u062a\u0645\u0648\u064a\u0644": "financing",
    "\u0625\u0646\u0634\u0627\u0621": "construction",
    "\u0639\u064a\u0627\u062f\u0627\u062a \u0623\u0633\u0646\u0627\u0646": "dental clinic",
    "\u0639\u064a\u0627\u062f\u0629 \u0623\u0633\u0646\u0627\u0646": "dental clinic",
    "\u0623\u0637\u0628\u0627\u0621 \u0623\u0633\u0646\u0627\u0646": "dentist",
    "\u0637\u0628\u064a\u0628 \u0623\u0633\u0646\u0627\u0646": "dentist",
    "\u0635\u0627\u0644\u0648\u0646\u0627\u062a \u062a\u062c\u0645\u064a\u0644": "beauty salon",
    "\u0635\u0627\u0644\u0648\u0646 \u062a\u062c\u0645\u064a\u0644": "beauty salon",
    "\u0645\u0643\u0627\u062a\u0628 \u0645\u062d\u0627\u0645\u0627\u0629": "law firm",
    "\u0645\u0643\u062a\u0628 \u0645\u062d\u0627\u0645\u0627\u0629": "law firm",
    "\u0645\u0637\u0627\u0639\u0645": "restaurant",
    "\u0645\u0637\u0639\u0645": "restaurant",
    "\u0639\u064a\u0627\u062f\u0627\u062a \u062c\u0644\u062f\u064a\u0629": "dermatology clinic",
    "\u0639\u064a\u0627\u062f\u0629 \u062c\u0644\u062f\u064a\u0629": "dermatology clinic",
    "\u0634\u0631\u0643\u0627\u062a \u062a\u0633\u0648\u064a\u0642 \u0631\u0642\u0645\u064a": "digital marketing agency",
    "\u0634\u0631\u0643\u0629 \u062a\u0633\u0648\u064a\u0642 \u0631\u0642\u0645\u064a": "digital marketing agency",
    "\u0645\u0631\u0627\u0643\u0632 \u0644\u064a\u0627\u0642\u0629 \u0628\u062f\u0646\u064a\u0629": "gym",
    "\u0646\u0627\u062f\u064a \u0631\u064a\u0627\u0636\u064a": "gym",
    "\u0639\u064a\u0627\u062f\u0627\u062a \u0628\u064a\u0637\u0631\u064a\u0629": "veterinary clinic",
    "\u0639\u064a\u0627\u062f\u0629 \u0628\u064a\u0637\u0631\u064a\u0629": "veterinary clinic",
    "\u0645\u0642\u0627\u0647\u064a": "cafe",
    "\u0645\u0642\u0647\u0649": "cafe",
    "\u0645\u0631\u0627\u0643\u0632 \u062a\u0639\u0644\u064a\u0645 \u0644\u063a\u0627\u062a": "language school",
    "\u0645\u0631\u0643\u0632 \u062a\u0639\u0644\u064a\u0645 \u0644\u063a\u0627\u062a": "language school",
}


@dataclass(frozen=True)
class QueryVariant:
    key: str
    text: str
    language: Literal["ar", "en", "mixed", "unknown"]


@dataclass(frozen=True)
class ExecutionTask:
    adapter_name: str
    stage: Literal["discover", "enrich", "validate"]
    query_variant: QueryVariant


@dataclass(frozen=True)
class DiscoveryBudget:
    max_concurrency: int
    max_calls_per_job: int
    max_candidates_after_merge: int
    max_enrichments_per_job: int
    global_deadline_seconds: int


class QueryPlanner:
    def plan(
        self,
        *,
        business_type: str,
        city: str,
        region: str | None,
        keyword_filter: str | None,
        bilingual_enabled: bool,
    ) -> list[QueryVariant]:
        base = self._normalize(" ".join(part for part in [business_type, city, region] if part))
        with_keywords = self._normalize(
            " ".join(part for part in [business_type, city, region, keyword_filter] if part)
        )
        variants: list[QueryVariant] = []
        variants.append(QueryVariant("original", base, self._detect_language(base)))
        if with_keywords and with_keywords != base:
            variants.append(
                QueryVariant("normalized", with_keywords, self._detect_language(with_keywords))
            )
        if bilingual_enabled:
            bilingual = self._bilingual_variant(with_keywords or base)
            if bilingual and bilingual not in {item.text for item in variants}:
                variants.append(
                    QueryVariant(
                        "bilingual_keyword_expansion", bilingual, self._detect_language(bilingual)
                    )
                )
        return variants

    def _normalize(self, value: str) -> str:
        cleaned = _PUNCT_RE.sub(" ", value)
        return _WS_RE.sub(" ", cleaned).strip()

    def _detect_language(self, text: str) -> Literal["ar", "en", "mixed", "unknown"]:
        has_ar = bool(_ARABIC_RE.search(text))
        has_latin = bool(re.search(r"[A-Za-z]", text))
        if has_ar and has_latin:
            return "mixed"
        if has_ar:
            return "ar"
        if has_latin:
            return "en"
        return "unknown"

    def _bilingual_variant(self, text: str) -> str:
        lowered = text.casefold()
        output = text.split()
        if _ARABIC_RE.search(text):
            for ar, en in _AR_TO_EN_KEYWORDS.items():
                if ar in text and en not in output:
                    output.append(en)
        else:
            for en, ar in _EN_TO_AR_KEYWORDS.items():
                if en in lowered and ar not in output:
                    output.append(ar)
        return self._normalize(" ".join(output))


class EngineExecutionPlanner:
    def plan(
        self,
        *,
        mode: DiscoveryMode,
        enabled_engines: list[str],
        query_variants: list[QueryVariant],
        max_calls_per_job: int,
        max_concurrency: int,
    ) -> list[ExecutionTask]:
        adapters: list[str]
        if mode == "single_path":
            adapters = ["google_maps_search"]
            variants = query_variants[:1]
        elif mode == "multi_query_single_engine":
            adapters = ["google_maps_search"]
            variants = query_variants
        else:
            # tavily_web is intentionally excluded here: it runs per-lead during the
            # later "validate" stage (see LeadDiscoveryOrchestrator._validate_web_presence),
            # not the query-fanout "discover" stage, because business-name-specific
            # validation requires a lead to already exist.
            allowed = {"google_maps_search", "google_web"}
            adapters = [engine for engine in enabled_engines if engine in allowed] or [
                "google_maps_search"
            ]
            variants = query_variants

        tasks: list[ExecutionTask] = []
        effective_adapters = adapters[: max(1, max_concurrency)]
        for variant in variants:
            for adapter_name in effective_adapters:
                tasks.append(
                    ExecutionTask(
                        adapter_name=adapter_name, stage="discover", query_variant=variant
                    )
                )
        return tasks[:max_calls_per_job]


class ResultMerger:
    def merge(
        self, collections: list[list[LeadCandidate]], *, max_candidates: int
    ) -> list[LeadCandidate]:
        merged: list[LeadCandidate] = []
        for group in collections:
            merged.extend(group)
            if len(merged) >= max_candidates:
                break
        return merged[:max_candidates]


class CrossSourceDeduper:
    def dedupe(self, candidates: list[LeadCandidate]) -> list[LeadCandidate]:
        by_key: dict[str, LeadCandidate] = {}
        ordered: list[LeadCandidate] = []
        for item in candidates:
            key = self._identity_key(item)
            existing = by_key.get(key)
            if existing is None:
                by_key[key] = item
                ordered.append(item)
                continue
            if item.completeness > existing.completeness or (
                item.completeness == existing.completeness and item.confidence > existing.confidence
            ):
                by_key[key] = item
                idx = ordered.index(existing)
                ordered[idx] = item
        return ordered

    def _identity_key(self, candidate: LeadCandidate) -> str:
        if candidate.place_id:
            return f"place:{candidate.place_id}"
        if candidate.website_domain:
            return f"domain:{candidate.website_domain.casefold()}"
        if candidate.phone:
            return f"phone:{re.sub(r'\D+', '', candidate.phone)}"
        city = (candidate.city or "").casefold().strip()
        name = candidate.company_name.casefold().strip()
        return f"namecity:{name}|{city}"


class CandidateRanker:
    def rank(self, candidates: list[LeadCandidate], *, max_candidates: int) -> list[LeadCandidate]:
        ranked = sorted(
            candidates,
            key=lambda item: (
                round(item.confidence, 4),
                round(item.completeness, 4),
                bool(item.website_domain),
                item.review_count,
            ),
            reverse=True,
        )
        return ranked[:max_candidates]


class CircuitState:
    def __init__(self) -> None:
        self._state: dict[str, tuple[int, datetime | None]] = {}

    def allow(self, key: str, *, threshold: int, cooldown_seconds: int) -> bool:
        failures, opened_at = self._state.get(key, (0, None))
        if failures < threshold:
            return True
        if opened_at is None:
            return True
        return datetime.now(tz=UTC) >= opened_at + timedelta(seconds=cooldown_seconds)

    def mark_success(self, key: str) -> None:
        self._state[key] = (0, None)

    def mark_failure(self, key: str) -> None:
        failures, opened_at = self._state.get(key, (0, None))
        if opened_at is None:
            self._state[key] = (failures + 1, None)
            return
        self._state[key] = (failures + 1, opened_at)

    def open_if_threshold(self, key: str, *, threshold: int) -> bool:
        failures, opened_at = self._state.get(key, (0, None))
        if failures >= threshold and opened_at is None:
            self._state[key] = (failures, datetime.now(tz=UTC))
            return True
        return False
