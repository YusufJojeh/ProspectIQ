from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.modules.leads.models import Lead
from app.modules.leads.repository import LeadsRepository
from app.modules.provider_serpapi.models import ProviderNormalizedFact
from app.modules.provider_serpapi.repository import ProviderEvidenceRepository
from app.modules.signals.models import LeadSignal, LeadSignalScore
from app.modules.signals.repository import LeadSignalRepository
from app.modules.signals.schemas import (
    LeadSignalResponse,
    LeadSignalScoreResponse,
    LeadSignalsResponse,
)

SIGNAL_TYPES = {
    "no_website",
    "weak_website",
    "low_rating",
    "high_reviews",
    "missing_phone",
    "poor_data_completeness",
    "high_local_visibility",
    "competitor_gap",
    "ready_for_outreach",
}


@dataclass(frozen=True)
class DetectedSignal:
    signal_type: str
    signal_strength: float
    evidence_text: str
    source_url: str | None = None


class LeadSignalDetectorService:
    def __init__(self) -> None:
        self.repository = LeadSignalRepository()
        self.leads_repository = LeadsRepository()
        self.evidence_repository = ProviderEvidenceRepository()

    def get_for_lead(
        self, db: Session, *, workspace_id: int, lead_public_id: str
    ) -> LeadSignalsResponse:
        lead = self._get_lead_or_raise(db, workspace_id, lead_public_id)
        return self._to_response(
            lead,
            self.repository.list_for_lead(db, workspace_id=workspace_id, lead_id=lead.id),
            self.repository.list_scores_for_lead(db, workspace_id=workspace_id, lead_id=lead.id),
        )

    def recompute_for_lead_public_id(
        self, db: Session, *, workspace_id: int, lead_public_id: str
    ) -> LeadSignalsResponse:
        lead = self._get_lead_or_raise(db, workspace_id, lead_public_id)
        facts = self.evidence_repository.list_normalized_facts_for_lead(db, lead.id)
        signals = self.recompute_for_lead(
            db, workspace_id=workspace_id, lead=lead, facts=facts
        )
        scores = self.repository.list_scores_for_lead(
            db, workspace_id=workspace_id, lead_id=lead.id
        )
        return self._to_response(lead, signals, scores)

    def recompute_for_lead(
        self,
        db: Session,
        *,
        workspace_id: int,
        lead: Lead,
        facts: list[ProviderNormalizedFact],
    ) -> list[LeadSignal]:
        if lead.workspace_id != workspace_id:
            raise NotFoundError("Lead was not found.")
        now = datetime.now(tz=UTC)
        detected = self.detect(lead, facts)
        signals = [
            LeadSignal(
                workspace_id=workspace_id,
                lead_id=lead.id,
                signal_type=item.signal_type,
                signal_strength=item.signal_strength,
                evidence_text=item.evidence_text,
                source_url=item.source_url,
                detected_at=now,
            )
            for item in detected
        ]
        scores = self._build_scores(
            workspace_id=workspace_id,
            lead_id=lead.id,
            detected=detected,
            now=now,
        )
        return self.repository.replace_for_lead(
            db,
            workspace_id=workspace_id,
            lead_id=lead.id,
            signals=signals,
            scores=scores,
        )

    def detect(
        self, lead: Lead, facts: list[ProviderNormalizedFact]
    ) -> list[DetectedSignal]:
        signals: list[DetectedSignal] = []
        has_website = bool(
            lead.has_website
            or lead.website_url
            or lead.website_domain
            or any(fact.website_url or fact.website_domain for fact in facts)
        )
        has_phone = bool(lead.phone or any(fact.phone for fact in facts))
        source_url = self._source_url(lead, facts)
        local_visibility = self._local_visibility_strength(lead, facts)
        weak_website_strength = self._weak_website_strength(lead, facts, has_website)

        if not has_website:
            signals.append(
                DetectedSignal(
                    signal_type="no_website",
                    signal_strength=1.0,
                    evidence_text="No official website was found on the lead record or normalized provider facts.",
                    source_url=source_url,
                )
            )
        elif weak_website_strength >= 0.55:
            signals.append(
                DetectedSignal(
                    signal_type="weak_website",
                    signal_strength=weak_website_strength,
                    evidence_text="Website presence looks weak or hard to discover relative to local visibility.",
                    source_url=source_url,
                )
            )

        if lead.rating is not None and lead.rating < 4.0:
            signals.append(
                DetectedSignal(
                    signal_type="low_rating",
                    signal_strength=round(min(1.0, (4.0 - lead.rating) / 1.5), 2),
                    evidence_text=f"Rating is {lead.rating:.1f}, below the 4.0 quality threshold.",
                    source_url=source_url,
                )
            )

        if lead.review_count >= 50:
            signals.append(
                DetectedSignal(
                    signal_type="high_reviews",
                    signal_strength=round(min(1.0, lead.review_count / 150), 2),
                    evidence_text=f"{lead.review_count} reviews indicate meaningful local demand.",
                    source_url=source_url,
                )
            )

        if not has_phone:
            signals.append(
                DetectedSignal(
                    signal_type="missing_phone",
                    signal_strength=0.85,
                    evidence_text="No phone number was present on the lead or normalized facts.",
                    source_url=source_url,
                )
            )

        if lead.data_completeness < 0.6:
            signals.append(
                DetectedSignal(
                    signal_type="poor_data_completeness",
                    signal_strength=round(1.0 - lead.data_completeness, 2),
                    evidence_text=f"Data completeness is {round(lead.data_completeness * 100)}%.",
                    source_url=source_url,
                )
            )

        if local_visibility >= 0.7:
            signals.append(
                DetectedSignal(
                    signal_type="high_local_visibility",
                    signal_strength=local_visibility,
                    evidence_text="Maps evidence, reviews, or knowledge-panel facts indicate strong local visibility.",
                    source_url=source_url,
                )
            )

        if (not has_website or weak_website_strength >= 0.65) and local_visibility >= 0.55:
            signals.append(
                DetectedSignal(
                    signal_type="competitor_gap",
                    signal_strength=round((weak_website_strength + local_visibility) / 2, 2),
                    evidence_text="Local demand is visible, but owned web presence appears weaker than the opportunity.",
                    source_url=source_url,
                )
            )

        if lead.data_confidence >= 0.6 and has_phone and (
            local_visibility >= 0.55 or weak_website_strength >= 0.55
        ):
            signals.append(
                DetectedSignal(
                    signal_type="ready_for_outreach",
                    signal_strength=round(
                        min(1.0, (lead.data_confidence + local_visibility + (1.0 if has_phone else 0.0)) / 3),
                        2,
                    ),
                    evidence_text="Lead has enough confidence and contactability to support outreach.",
                    source_url=source_url,
                )
            )

        return signals

    def _build_scores(
        self,
        *,
        workspace_id: int,
        lead_id: int,
        detected: list[DetectedSignal],
        now: datetime,
    ) -> list[LeadSignalScore]:
        grouped: dict[str, list[DetectedSignal]] = defaultdict(list)
        for signal in detected:
            grouped[signal.signal_type].append(signal)
        return [
            LeadSignalScore(
                workspace_id=workspace_id,
                lead_id=lead_id,
                signal_type=signal_type,
                score=round(max(item.signal_strength for item in items) * 100, 2),
                confidence=round(sum(item.signal_strength for item in items) / len(items), 2),
                evidence_count=len(items),
                calculated_at=now,
            )
            for signal_type, items in grouped.items()
        ]

    def _local_visibility_strength(
        self, lead: Lead, facts: list[ProviderNormalizedFact]
    ) -> float:
        maps_fact = any(fact.source_type in {"maps_search", "maps_place"} for fact in facts)
        knowledge_graph = any(bool(fact.facts_json.get("knowledge_graph_present")) for fact in facts)
        review_component = min(1.0, lead.review_count / 80)
        rating_component = min(1.0, (lead.rating or 0.0) / 5)
        source_component = 1.0 if maps_fact else 0.35
        knowledge_component = 1.0 if knowledge_graph else 0.0
        return round(
            (review_component * 0.35)
            + (rating_component * 0.25)
            + (source_component * 0.25)
            + (knowledge_component * 0.15),
            2,
        )

    def _weak_website_strength(
        self, lead: Lead, facts: list[ProviderNormalizedFact], has_website: bool
    ) -> float:
        if not has_website:
            return 1.0
        discoverability_values = [
            float(value)
            for fact in facts
            for value in (fact.facts_json.get("visibility_confidence"),)
            if isinstance(value, int | float)
        ]
        if discoverability_values:
            return round(1.0 - max(discoverability_values), 2)
        if lead.website_domain and lead.company_name.split()[0].casefold() in lead.website_domain.casefold():
            return 0.25
        return 0.55

    def _source_url(self, lead: Lead, facts: list[ProviderNormalizedFact]) -> str | None:
        if lead.website_url:
            return lead.website_url
        for fact in facts:
            value = fact.facts_json.get("source_url") or fact.facts_json.get("link")
            if isinstance(value, str) and value:
                return value
            if fact.website_url:
                return fact.website_url
        return None

    def _get_lead_or_raise(self, db: Session, workspace_id: int, lead_public_id: str) -> Lead:
        lead = self.leads_repository.get_by_public_id_for_workspace(
            db, workspace_id=workspace_id, public_id=lead_public_id
        )
        if lead is None:
            raise NotFoundError("Lead was not found.")
        return lead

    def _to_response(
        self,
        lead: Lead,
        signals: list[LeadSignal],
        scores: list[LeadSignalScore],
    ) -> LeadSignalsResponse:
        return LeadSignalsResponse(
            lead_id=lead.public_id,
            items=[
                LeadSignalResponse(
                    public_id=signal.public_id,
                    signal_type=signal.signal_type,
                    signal_strength=signal.signal_strength,
                    evidence_text=signal.evidence_text,
                    source_url=signal.source_url,
                    detected_at=signal.detected_at,
                )
                for signal in signals
            ],
            scores=[
                LeadSignalScoreResponse(
                    signal_type=score.signal_type,
                    score=score.score,
                    confidence=score.confidence,
                    evidence_count=score.evidence_count,
                    calculated_at=score.calculated_at,
                )
                for score in scores
            ],
        )
