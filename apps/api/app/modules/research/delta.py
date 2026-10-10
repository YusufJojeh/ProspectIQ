from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.leads.models import Lead
from app.modules.provider_serpapi.models import ProviderFetch, ProviderNormalizedFact
from app.modules.provider_serpapi.repository import ProviderEvidenceRepository
from app.modules.research.evidence_graph import EvidenceGraphBuilder
from app.modules.research.models import ResearchChangeEvent
from app.modules.research.repository import ResearchRepository
from app.modules.scoring.rescore import rescore_lead
from app.modules.signals.repository import LeadSignalRepository

logger = logging.getLogger(__name__)

Direction = Literal["improved", "declined", "neutral"]

# Claim types where a numeric increase is an improvement (more reviews, higher
# rating). Any claim type not listed here is treated categorically: any
# change at all is "neutral" direction (a fact changed, not necessarily for
# better or worse) unless a specific rule below says otherwise.
_HIGHER_IS_BETTER: dict[str, float] = {
    "rating": 5.0,
    "review_count": 200.0,
    "branch_count": 10.0,
}

# Below this fraction of the claim's typical scale, a numeric change is noise
# (e.g. rating 4.61 -> 4.63) and is dropped before it ever becomes a
# ChangeCandidate.
_NUMERIC_NOISE_FRACTION = 0.02

_EVENT_TYPE_BY_CLAIM: dict[str, str] = {
    "rating": "rating_changed",
    "review_count": "review_count_changed",
    "website_url": "website_changed",
    "website_domain": "website_changed",
    "phone": "contact_info_changed",
    "address": "address_changed",
    "company_name": "identity_changed",
    "category": "category_changed",
    "online_booking": "digital_capability_changed",
    "branch_count": "branch_count_changed",
    "services": "services_changed",
    "social_presence": "social_presence_changed",
    "contact_channels": "contactability_changed",
    "has_ecommerce": "digital_capability_changed",
    "has_whatsapp": "contactability_changed",
    "review_sentiment": "review_sentiment_changed",
    "recurring_review_pain_points": "review_pain_points_changed",
    "hiring_signal": "hiring_signal_changed",
    "digital_maturity": "digital_maturity_changed",
}

_BOOLEAN_CAPABILITY_CLAIMS = {"online_booking", "has_ecommerce", "has_whatsapp"}
_COLLECTION_CLAIMS = {"services", "contact_channels"}


@dataclass(frozen=True)
class ChangeCandidate:
    claim_type: str
    previous_value: str | None
    new_value: str | None
    event_type: str
    direction: Direction
    significance: float


class FactDiffEngine:
    """Deterministically decides whether two point-in-time snapshots of a
    lead's canonical facts differ meaningfully, and how to classify the
    difference. This is the sole authority on "did something change" --
    ChangeExplainer only ever narrates a candidate this engine already
    produced.
    """

    def diff(
        self,
        *,
        previous: dict[str, tuple[str, float]],
        current: dict[str, tuple[str, float]],
    ) -> list[ChangeCandidate]:
        candidates: list[ChangeCandidate] = []
        for claim_type, (new_value, _confidence) in current.items():
            if claim_type not in previous:
                direction: Direction = (
                    "improved" if self._is_positive_capability(claim_type, new_value) else "neutral"
                )
                candidates.append(
                    ChangeCandidate(
                        claim_type=claim_type,
                        previous_value=None,
                        new_value=new_value,
                        event_type=_EVENT_TYPE_BY_CLAIM.get(claim_type, "evidence_added"),
                        direction=direction,
                        significance=0.5 if direction == "improved" else 0.2,
                    )
                )
                continue

            previous_value, _ = previous[claim_type]
            if previous_value == new_value:
                continue

            candidate = self._classify_change(claim_type, previous_value, new_value)
            if candidate is not None:
                candidates.append(candidate)

        return candidates

    def _classify_change(
        self, claim_type: str, previous_value: str, new_value: str
    ) -> ChangeCandidate | None:
        if claim_type in _HIGHER_IS_BETTER:
            return self._classify_numeric_change(claim_type, previous_value, new_value)
        if claim_type in _BOOLEAN_CAPABILITY_CLAIMS:
            return self._classify_boolean_change(claim_type, previous_value, new_value)
        if claim_type == "hiring_signal":
            return self._classify_active_change(claim_type, previous_value, new_value)
        if claim_type == "digital_maturity":
            return self._classify_json_score_change(claim_type, previous_value, new_value)
        if claim_type in _COLLECTION_CLAIMS:
            return self._classify_collection_change(claim_type, previous_value, new_value)

        return ChangeCandidate(
            claim_type=claim_type,
            previous_value=previous_value,
            new_value=new_value,
            event_type=_EVENT_TYPE_BY_CLAIM.get(claim_type, "value_changed"),
            direction="neutral",
            significance=0.5,
        )

    def _classify_boolean_change(
        self, claim_type: str, previous_value: str, new_value: str
    ) -> ChangeCandidate:
        before = previous_value.casefold() == "true"
        after = new_value.casefold() == "true"
        direction: Direction = "improved" if after and not before else "declined" if before and not after else "neutral"
        return ChangeCandidate(
            claim_type=claim_type,
            previous_value=previous_value,
            new_value=new_value,
            event_type=_EVENT_TYPE_BY_CLAIM[claim_type],
            direction=direction,
            significance=0.6 if direction != "neutral" else 0.3,
        )

    def _classify_active_change(
        self, claim_type: str, previous_value: str, new_value: str
    ) -> ChangeCandidate:
        before = self._json_dict(previous_value).get("active") is True
        after = self._json_dict(new_value).get("active") is True
        direction: Direction = "improved" if after and not before else "declined" if before and not after else "neutral"
        return ChangeCandidate(
            claim_type=claim_type,
            previous_value=previous_value,
            new_value=new_value,
            event_type=_EVENT_TYPE_BY_CLAIM[claim_type],
            direction=direction,
            significance=0.6 if direction != "neutral" else 0.4,
        )

    def _classify_json_score_change(
        self, claim_type: str, previous_value: str, new_value: str
    ) -> ChangeCandidate:
        before = self._json_dict(previous_value).get("score")
        after = self._json_dict(new_value).get("score")
        if not isinstance(before, int | float) or not isinstance(after, int | float):
            return self._categorical(claim_type, previous_value, new_value)
        delta = float(after) - float(before)
        direction: Direction = "improved" if delta > 0 else "declined" if delta < 0 else "neutral"
        return ChangeCandidate(
            claim_type=claim_type,
            previous_value=previous_value,
            new_value=new_value,
            event_type=_EVENT_TYPE_BY_CLAIM[claim_type],
            direction=direction,
            significance=round(min(1.0, abs(delta) / 40.0), 4),
        )

    def _classify_collection_change(
        self, claim_type: str, previous_value: str, new_value: str
    ) -> ChangeCandidate:
        before = self._json_list(previous_value)
        after = self._json_list(new_value)
        direction: Direction = "improved" if len(after) > len(before) else "declined" if len(after) < len(before) else "neutral"
        return ChangeCandidate(
            claim_type=claim_type,
            previous_value=previous_value,
            new_value=new_value,
            event_type=_EVENT_TYPE_BY_CLAIM[claim_type],
            direction=direction,
            significance=round(min(1.0, 0.3 + abs(len(after) - len(before)) * 0.15), 4),
        )

    def _categorical(
        self, claim_type: str, previous_value: str, new_value: str
    ) -> ChangeCandidate:
        return ChangeCandidate(
            claim_type=claim_type,
            previous_value=previous_value,
            new_value=new_value,
            event_type=_EVENT_TYPE_BY_CLAIM.get(claim_type, "value_changed"),
            direction="neutral",
            significance=0.5,
        )

    def _is_positive_capability(self, claim_type: str, value: str) -> bool:
        if claim_type in _BOOLEAN_CAPABILITY_CLAIMS:
            return value.casefold() == "true"
        if claim_type == "hiring_signal":
            return self._json_dict(value).get("active") is True
        return False

    def _json_dict(self, value: str) -> dict[str, object]:
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _json_list(self, value: str) -> list[object]:
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return []
        return parsed if isinstance(parsed, list) else []

    def _classify_numeric_change(
        self, claim_type: str, previous_value: str, new_value: str
    ) -> ChangeCandidate | None:
        try:
            previous_number = float(previous_value)
            new_number = float(new_value)
        except ValueError:
            return ChangeCandidate(
                claim_type=claim_type,
                previous_value=previous_value,
                new_value=new_value,
                event_type=_EVENT_TYPE_BY_CLAIM.get(claim_type, "value_changed"),
                direction="neutral",
                significance=0.5,
            )

        scale = _HIGHER_IS_BETTER[claim_type]
        delta = new_number - previous_number
        magnitude = abs(delta) / scale
        if magnitude < _NUMERIC_NOISE_FRACTION:
            return None

        direction: Direction = "improved" if delta > 0 else "declined"
        significance = round(max(0.0, min(1.0, magnitude * 4)), 4)
        return ChangeCandidate(
            claim_type=claim_type,
            previous_value=previous_value,
            new_value=new_value,
            event_type=_EVENT_TYPE_BY_CLAIM[claim_type],
            direction=direction,
            significance=significance,
        )


class ChangeExplainer:
    """Produces the human-readable `explanation` for an already-decided
    ChangeCandidate. Never decides whether a change occurred or how
    significant it is -- FactDiffEngine already did that. Falls back to a
    deterministic templated sentence whenever the LLM runtime isn't
    available/configured, or on any error, so a research run never fails
    because of the explanation step.
    """

    def explain(self, candidate: ChangeCandidate, *, company_name: str) -> str:
        settings = get_settings()
        if settings.research_agent_runtime == "openai" and settings.openai_api_key:
            try:
                return self._explain_with_llm(candidate, company_name=company_name)
            except Exception:
                logger.exception(
                    "delta_intelligence.explain_failed claim_type=%s", candidate.claim_type
                )
        return self._explain_with_template(candidate, company_name=company_name)

    def _explain_with_template(self, candidate: ChangeCandidate, *, company_name: str) -> str:
        if candidate.previous_value is None:
            return (
                f"New evidence found for {company_name}: {candidate.claim_type} is now "
                f"'{candidate.new_value}'."
            )
        direction_phrase = {
            "improved": "improved",
            "declined": "declined",
            "neutral": "changed",
        }[candidate.direction]
        return (
            f"{company_name}'s {candidate.claim_type} {direction_phrase} from "
            f"'{candidate.previous_value}' to '{candidate.new_value}'."
        )

    def _explain_with_llm(self, candidate: ChangeCandidate, *, company_name: str) -> str:
        from openai import OpenAI  # type: ignore[import-not-found,unused-ignore]

        settings = get_settings()
        client = OpenAI(api_key=settings.openai_api_key)
        prompt = (
            f"In one short sentence, explain why this change matters for a sales rep "
            f"prospecting {company_name}. Do not speculate about whether the change is "
            f"real -- it is already confirmed. Claim: {candidate.claim_type}. "
            f"Previous value: {candidate.previous_value!r}. New value: {candidate.new_value!r}. "
            f"Direction: {candidate.direction}."
        )
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=80,
            timeout=settings.research_agent_max_runtime_seconds,
        )
        content = (response.choices[0].message.content or "").strip()
        return content or self._explain_with_template(candidate, company_name=company_name)


class DeltaIntelligenceService:
    """Wires FactDiffEngine + ChangeExplainer into the research-run
    lifecycle: builds this run's canonical snapshot, diffs it against the
    previous OK run, persists ResearchRun/ResearchFactSnapshot/
    ResearchChangeEvent rows, and triggers a rescore for significant,
    non-neutral changes.
    """

    def __init__(
        self,
        *,
        research_repository: ResearchRepository | None = None,
        evidence_repository: ProviderEvidenceRepository | None = None,
        signal_repository: LeadSignalRepository | None = None,
        graph_builder: EvidenceGraphBuilder | None = None,
        diff_engine: FactDiffEngine | None = None,
        explainer: ChangeExplainer | None = None,
    ) -> None:
        self._research_repository = research_repository or ResearchRepository()
        self._evidence_repository = evidence_repository or ProviderEvidenceRepository()
        self._signal_repository = signal_repository or LeadSignalRepository()
        self._graph_builder = graph_builder or EvidenceGraphBuilder()
        self._diff_engine = diff_engine or FactDiffEngine()
        self._explainer = explainer or ChangeExplainer()

    def process_completed_run(
        self,
        db: Session,
        *,
        workspace_id: int,
        lead: Lead,
        depth: str,
        mode: str,
        status: str,
        providers_used: list[str],
    ) -> list[ResearchChangeEvent]:
        facts = self._evidence_repository.list_normalized_facts_for_lead(db, lead.id)
        fetches_by_id = self._fetches_by_id(db, facts)
        signals = self._signal_repository.list_for_lead(
            db, workspace_id=workspace_id, lead_id=lead.id
        )

        graph = self._graph_builder.build(
            lead_public_id=lead.public_id,
            facts=facts,
            fetches_by_id=fetches_by_id,
            signals=signals,
        )
        current_snapshot = {
            canonical_fact.claim_type: (canonical_fact.value, canonical_fact.confidence)
            for group in graph.groups
            for canonical_fact in group.facts
        }

        previous_run = self._research_repository.get_latest_ok_run(db, lead.id)
        previous_snapshot = (
            self._research_repository.load_snapshot_map(db, previous_run.id)
            if previous_run is not None
            else {}
        )

        current_run = self._research_repository.create_run(
            db,
            workspace_id=workspace_id,
            lead_id=lead.id,
            depth=depth,
            mode=mode,
            status=status,
            providers_used=providers_used,
            evidence_confidence=graph.evidence_confidence,
            research_coverage=graph.research_coverage,
        )
        self._research_repository.save_snapshot(
            db,
            research_run_id=current_run.id,
            workspace_id=workspace_id,
            lead_id=lead.id,
            snapshot_map=current_snapshot,
        )

        if previous_run is None:
            return []

        settings = get_settings()
        candidates = self._diff_engine.diff(previous=previous_snapshot, current=current_snapshot)
        meaningful = [
            candidate
            for candidate in candidates
            if candidate.significance >= settings.research_delta_min_significance
        ]
        if not meaningful:
            return []

        should_rescore = any(
            candidate.direction != "neutral"
            and candidate.significance >= settings.research_delta_rescore_significance
            for candidate in meaningful
        )
        rescored = False
        if should_rescore:
            try:
                rescore_lead(db, workspace_id=workspace_id, lead=lead)
                rescored = True
            except Exception:
                logger.exception("delta_intelligence.rescore_failed lead_id=%s", lead.id)

        events: list[ResearchChangeEvent] = []
        for candidate in meaningful:
            explanation = self._explainer.explain(candidate, company_name=lead.company_name)
            events.append(
                self._research_repository.save_change_event(
                    db,
                    workspace_id=workspace_id,
                    lead_id=lead.id,
                    previous_research_run_id=previous_run.id,
                    current_research_run_id=current_run.id,
                    claim_type=candidate.claim_type,
                    previous_value=candidate.previous_value,
                    new_value=candidate.new_value,
                    event_type=candidate.event_type,
                    direction=candidate.direction,
                    significance=candidate.significance,
                    explanation=explanation,
                    triggered_rescore=rescored
                    and candidate.direction != "neutral"
                    and candidate.significance >= settings.research_delta_rescore_significance,
                )
            )
        return events

    def _fetches_by_id(
        self, db: Session, facts: list[ProviderNormalizedFact]
    ) -> dict[int, ProviderFetch]:
        fetch_ids = {fact.provider_fetch_id for fact in facts}
        if not fetch_ids:
            return {}
        return {
            fetch.id: fetch
            for fetch in db.query(ProviderFetch).filter(ProviderFetch.id.in_(fetch_ids))
        }
