from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.modules.icp.repository import IcpProfileRepository
from app.modules.leads.models import Lead
from app.modules.provider_serpapi.repository import ProviderEvidenceRepository
from app.modules.scoring.repository import ScoringRepository
from app.modules.signals.repository import LeadSignalRepository

_MAX_EVIDENCE = 20


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    source_type: str
    source_url: str | None
    evidence_text: str
    confidence: float


class EvidenceBuilder:
    """Build grounded evidence for an AI analysis snapshot from real stored data.

    Every record is derived from data already persisted for the lead (provider
    normalized facts, detected signals, deterministic score breakdown, ICP
    matches). Nothing here is invented by the model, so persisted evidence can
    be trusted as the factual basis for an analysis.
    """

    def __init__(self) -> None:
        self.signal_repository = LeadSignalRepository()
        self.scoring_repository = ScoringRepository()
        self.evidence_repository = ProviderEvidenceRepository()
        self.icp_repository = IcpProfileRepository()

    def build(self, db: Session, *, workspace_id: int, lead: Lead) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []
        records.extend(self._from_signals(db, workspace_id=workspace_id, lead=lead))
        records.extend(self._from_score_breakdown(db, lead=lead))
        records.extend(self._from_icp_matches(db, workspace_id=workspace_id, lead=lead))
        records.extend(self._from_provider_facts(db, lead=lead))
        return records[:_MAX_EVIDENCE]

    def _from_signals(
        self, db: Session, *, workspace_id: int, lead: Lead
    ) -> list[EvidenceRecord]:
        signals = self.signal_repository.list_for_lead(
            db, workspace_id=workspace_id, lead_id=lead.id
        )
        return [
            EvidenceRecord(
                source_type=f"signal:{signal.signal_type}",
                source_url=signal.source_url,
                evidence_text=signal.evidence_text,
                confidence=_clamp(
                    signal.signal_strength
                    if signal.signal_strength <= 1
                    else signal.signal_strength / 100
                ),
            )
            for signal in signals
        ]

    def _from_score_breakdown(self, db: Session, *, lead: Lead) -> list[EvidenceRecord]:
        try:
            breakdown = self.scoring_repository.get_latest_score_breakdown(db, lead.id)
        except NotFoundError:
            return []
        ranked = sorted(
            breakdown.breakdown,
            key=lambda item: abs(item.contribution),
            reverse=True,
        )[:5]
        return [
            EvidenceRecord(
                source_type="score_factor",
                source_url=None,
                evidence_text=f"{item.label}: {item.reason}",
                confidence=_clamp(min(1.0, abs(item.contribution) / 100 + 0.5)),
            )
            for item in ranked
            if item.reason
        ]

    def _from_icp_matches(
        self, db: Session, *, workspace_id: int, lead: Lead
    ) -> list[EvidenceRecord]:
        matches = self.icp_repository.list_matches_for_lead(
            db, workspace_id=workspace_id, lead_id=lead.id
        )
        records: list[EvidenceRecord] = []
        for match in matches[:2]:
            reasons = ", ".join(_stringify_reasons(match.match_reasons_json)) or "no detail"
            verdict = "matches" if match.matched else "does not match"
            records.append(
                EvidenceRecord(
                    source_type="icp_match",
                    source_url=None,
                    evidence_text=(
                        f"Lead {verdict} ICP (fit score {round(match.fit_score)}). "
                        f"Reasons: {reasons}."
                    ),
                    confidence=_clamp(match.fit_score / 100),
                )
            )
        return records

    def _from_provider_facts(self, db: Session, *, lead: Lead) -> list[EvidenceRecord]:
        facts = self.evidence_repository.list_normalized_facts_for_lead(db, lead.id)
        records: list[EvidenceRecord] = []
        for fact in facts[:6]:
            details: list[str] = []
            if fact.rating is not None:
                details.append(f"rating {fact.rating}")
            if fact.review_count:
                details.append(f"{fact.review_count} reviews")
            if fact.city:
                details.append(fact.city)
            if fact.website_domain:
                details.append(fact.website_domain)
            summary = ", ".join(details) if details else "no additional attributes"
            source_url = fact.website_url or _fact_source_url(fact.facts_json)
            records.append(
                EvidenceRecord(
                    source_type=f"provider:{fact.source_type}",
                    source_url=source_url,
                    evidence_text=f"{fact.company_name} ({summary}).",
                    confidence=_clamp(fact.confidence),
                )
            )
        return records


def _clamp(value: float) -> float:
    return round(max(0.0, min(1.0, float(value))), 2)


def _stringify_reasons(reasons: dict[str, object]) -> list[str]:
    labels: list[str] = []
    for key, value in reasons.items():
        if isinstance(value, bool):
            labels.append(f"{key}: {'yes' if value else 'no'}")
        elif isinstance(value, str | int | float):
            labels.append(f"{key}: {value}")
        elif isinstance(value, list):
            labels.append(f"{key}: {', '.join(str(item) for item in value[:3])}")
    return labels[:5]


def _fact_source_url(facts_json: dict[str, object]) -> str | None:
    for key in ("source_url", "link", "website"):
        value = facts_json.get(key)
        if isinstance(value, str) and value:
            return value
    return None
