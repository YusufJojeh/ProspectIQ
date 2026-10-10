from __future__ import annotations

import json
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.modules.knowledge.constants import (
    CAPABILITIES,
    CASE_STUDIES,
    PORTFOLIO,
    SERVICES,
)
from app.modules.knowledge.retrieval import KnowledgeRetriever, RetrievedChunk, excerpt
from app.modules.research.evidence_graph import CanonicalFact, EvidenceGraph

# --- Opportunity -> capability matching ---------------------------------
#
# The division of labour here is the whole point of the module.
#
#   The BACKEND decides which opportunities exist. An opportunity is a
#   deterministic predicate over canonical facts the Evidence Graph already
#   computed, and it carries that fact's own confidence -- never a number the
#   model made up.
#
#   RETRIEVAL decides which of our documents speak to that opportunity, with
#   citations.
#
#   The MODEL only writes the pitch, from opportunities it did not choose and
#   capabilities it did not invent.
#
# That is why a rule below is a predicate plus a query, and never a sentence
# about the customer.


@dataclass(frozen=True, slots=True)
class OpportunityRule:
    key: str
    label: str
    #: The canonical fact this rule reads. A rule that has no fact to read
    #: produces no opportunity -- absence of evidence is never a finding.
    claim_type: str
    #: Values of that fact which mean the opportunity is present. A fact that
    #: is absent entirely never triggers a rule: "we did not find a website"
    #: and "this business has no website" are different claims, and only the
    #: second one is a finding.
    trigger_values: frozenset[str]
    search_query: str
    why: str


_RULES: tuple[OpportunityRule, ...] = (
    OpportunityRule(
        key="no_online_booking",
        label="No online booking",
        claim_type="online_booking",
        trigger_values=frozenset({"false"}),
        search_query="online booking appointment scheduling system",
        why="Customers cannot book without calling, so out-of-hours demand is lost.",
    ),
    OpportunityRule(
        key="no_website",
        label="No website",
        claim_type="website_url",
        trigger_values=frozenset({"", "none", "null", "false"}),
        search_query="website design and build for local business",
        why="There is no owned web presence to convert local search demand.",
    ),
    OpportunityRule(
        key="no_whatsapp_channel",
        label="No WhatsApp channel",
        claim_type="has_whatsapp",
        trigger_values=frozenset({"false"}),
        search_query="whatsapp business messaging channel setup",
        why="The market's dominant messaging channel is not available to customers.",
    ),
    OpportunityRule(
        key="no_ecommerce",
        label="No online sales",
        claim_type="has_ecommerce",
        trigger_values=frozenset({"false"}),
        search_query="ecommerce online store setup and payments",
        why="Products can only be sold in person.",
    ),
    OpportunityRule(
        key="weak_review_sentiment",
        label="Negative review sentiment",
        claim_type="review_sentiment",
        trigger_values=frozenset({"negative", "mixed"}),
        search_query="review reputation management response and recovery",
        why="Public sentiment is suppressing conversion from search.",
    ),
    OpportunityRule(
        key="no_social_presence",
        label="No social presence",
        claim_type="social_presence",
        trigger_values=frozenset({"[]", "{}", ""}),
        search_query="social media management content for local business",
        why="No social channel is carrying the brand between visits.",
    ),
    OpportunityRule(
        key="hiring_growth",
        label="Actively hiring",
        claim_type="hiring_signal",
        trigger_values=frozenset({"true"}),
        search_query="scaling operations during growth and expansion",
        why="Hiring indicates budget and expansion, which is a timing signal.",
    ),
)

#: Digital maturity is handled separately because its value is a JSON object
#: with a band, not a scalar.
_LOW_MATURITY_QUERY = "digital foundation package for businesses with low online maturity"


@dataclass(frozen=True, slots=True)
class CapabilityMatch:
    opportunity_key: str
    opportunity_label: str
    #: Why the backend believes the opportunity exists, in terms of the fact
    #: it read -- not a generated sentence.
    basis_claim_type: str
    basis_value: str | None
    #: The Evidence Graph's own confidence in that fact, carried through
    #: unchanged. The model must not restate or inflate it.
    confidence: float
    rationale: str
    capabilities: list[dict[str, object]] = field(default_factory=list)
    proof: list[dict[str, object]] = field(default_factory=list)


@dataclass
class CapabilityMatcher:
    """Matches a lead's evidenced problems to what this workspace can deliver."""

    retriever: KnowledgeRetriever = field(default_factory=KnowledgeRetriever)
    settings: Settings = field(default_factory=get_settings)

    def match(
        self,
        db: Session,
        *,
        workspace_id: int,
        graph: EvidenceGraph,
        user_id: int | None,
        user_role: str | None,
        limit_per_opportunity: int = 3,
    ) -> list[CapabilityMatch]:
        facts = {
            fact.claim_type: fact for group in graph.groups for fact in group.facts
        }
        matches: list[CapabilityMatch] = []

        for rule in _RULES:
            fact = facts.get(rule.claim_type)
            if not self._triggered(rule, fact):
                continue
            matches.append(
                self._build(
                    db,
                    workspace_id=workspace_id,
                    user_id=user_id,
                    user_role=user_role,
                    key=rule.key,
                    label=rule.label,
                    claim_type=rule.claim_type,
                    value=fact.value if fact else None,
                    confidence=fact.confidence if fact else 0.0,
                    rationale=rule.why,
                    query=rule.search_query,
                    limit=limit_per_opportunity,
                )
            )

        maturity = facts.get("digital_maturity")
        band = self._maturity_band(maturity)
        if band == "low":
            assert maturity is not None
            matches.append(
                self._build(
                    db,
                    workspace_id=workspace_id,
                    user_id=user_id,
                    user_role=user_role,
                    key="low_digital_maturity",
                    label="Low digital maturity",
                    claim_type="digital_maturity",
                    value=maturity.value,
                    confidence=maturity.confidence,
                    rationale=(
                        "The deterministic digital-maturity score for this lead falls in the "
                        "low band, so several foundations are missing at once."
                    ),
                    query=_LOW_MATURITY_QUERY,
                    limit=limit_per_opportunity,
                )
            )

        # Highest-confidence opportunities first: the salesperson should lead
        # with what we can actually stand behind.
        matches.sort(key=lambda item: (item.confidence, item.opportunity_key), reverse=True)
        return matches

    # --- helpers -------------------------------------------------------

    def _triggered(self, rule: OpportunityRule, fact: CanonicalFact | None) -> bool:
        if fact is None:
            return False
        return (fact.value or "").strip().lower() in rule.trigger_values

    def _maturity_band(self, fact: CanonicalFact | None) -> str | None:
        if fact is None:
            return None
        try:
            payload = json.loads(fact.value)
        except (TypeError, ValueError):
            return None
        band = payload.get("band") if isinstance(payload, dict) else None
        return band if isinstance(band, str) else None

    def _build(
        self,
        db: Session,
        *,
        workspace_id: int,
        user_id: int | None,
        user_role: str | None,
        key: str,
        label: str,
        claim_type: str,
        value: str | None,
        confidence: float,
        rationale: str,
        query: str,
        limit: int,
    ) -> CapabilityMatch:
        capabilities = self.retriever.search(
            db,
            workspace_id=workspace_id,
            query=query,
            user_id=user_id,
            user_role=user_role,
            document_types=(SERVICES, CAPABILITIES),
            limit=limit,
        )
        proof = self.retriever.search(
            db,
            workspace_id=workspace_id,
            query=query,
            user_id=user_id,
            user_role=user_role,
            document_types=(CASE_STUDIES, PORTFOLIO),
            limit=limit,
        )
        return CapabilityMatch(
            opportunity_key=key,
            opportunity_label=label,
            basis_claim_type=claim_type,
            basis_value=value,
            confidence=confidence,
            rationale=rationale,
            capabilities=[self._citation(item) for item in capabilities.results],
            proof=[self._citation(item) for item in proof.results],
        )

    def _citation(self, item: RetrievedChunk) -> dict[str, object]:
        return {
            "chunk_id": item.chunk_id,
            "document_id": item.document_id,
            "document_title": item.document_title,
            "document_type": item.document_type,
            "section": item.section,
            "excerpt": excerpt(
                item.content, max_chars=self.settings.knowledge_excerpt_max_chars
            ),
            "score": item.score,
        }


__all__ = ["CapabilityMatch", "CapabilityMatcher", "OpportunityRule"]
