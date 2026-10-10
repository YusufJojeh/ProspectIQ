from __future__ import annotations

from collections import defaultdict

from app.modules.provider_serpapi.models import ProviderFetch, ProviderNormalizedFact
from app.modules.research.schemas import ContradictionSummary, ContradictionValue

_COMPARABLE_CLAIMS = ("phone", "website_domain", "category", "address")


class ContradictionDetector:
    """Flags disagreeing values for the same claim across provider facts.

    A claim only contradicts when at least two distinct, non-empty
    normalized values come from at least two different providers -- two
    facts from the same provider (e.g. two Apify pages on the same site)
    restating the same value is not a contradiction.
    """

    def detect(
        self,
        facts: list[ProviderNormalizedFact],
        fetches_by_id: dict[int, ProviderFetch],
    ) -> list[ContradictionSummary]:
        summaries: list[ContradictionSummary] = []
        for claim_type in _COMPARABLE_CLAIMS:
            grouped: dict[str, ContradictionValue] = {}
            providers_by_value: dict[str, set[str]] = defaultdict(set)
            for fact in facts:
                value = getattr(fact, claim_type, None)
                if not value:
                    continue
                normalized_key = str(value).strip().casefold()
                if not normalized_key:
                    continue
                fetch = fetches_by_id.get(fact.provider_fetch_id)
                provider = fetch.provider if fetch else "unknown"
                providers_by_value[normalized_key].add(provider)
                grouped.setdefault(
                    normalized_key,
                    ContradictionValue(
                        value=str(value),
                        provider=provider,
                        source_url=fact.website_url,
                        confidence=fact.confidence,
                    ),
                )

            distinct_providers = {provider for providers in providers_by_value.values() for provider in providers}
            if len(grouped) > 1 and len(distinct_providers) > 1:
                summaries.append(
                    ContradictionSummary(claim_type=claim_type, values=list(grouped.values()))
                )
        return summaries
