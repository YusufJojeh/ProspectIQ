from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.icp.service import LeadIcpMatcherService
from app.modules.leads.models import Lead
from app.modules.provider_serpapi.repository import ProviderEvidenceRepository
from app.modules.scoring.fact_builder import EvidenceFactBuilder
from app.modules.scoring.models import LeadScore
from app.modules.scoring.schemas import ScoringThresholds, ScoringWeights
from app.modules.scoring.service import ScoringConfigService, ScoringEngine, persist_lead_score
from app.modules.signals.service import LeadSignalDetectorService


def rescore_lead(
    db: Session,
    *,
    workspace_id: int,
    lead: Lead,
    evidence_repository: ProviderEvidenceRepository | None = None,
    signal_detector: LeadSignalDetectorService | None = None,
    icp_matcher: LeadIcpMatcherService | None = None,
    fact_builder: EvidenceFactBuilder | None = None,
    scoring_engine: ScoringEngine | None = None,
    scoring_config_service: ScoringConfigService | None = None,
) -> LeadScore:
    """Recompute and persist a lead's score from its current evidence outside
    a SearchJob context -- e.g. triggered by Delta Intelligence after a
    meaningful evidence change. Mirrors LeadDiscoveryOrchestrator._score_leads
    for exactly one already-known lead, using `get_active_version` (raises if
    none exists) rather than `ensure_active_version`, since a job-less rescore
    has no `requested_by_user_id` to attribute an auto-created config to.
    """
    evidence_repository = evidence_repository or ProviderEvidenceRepository()
    signal_detector = signal_detector or LeadSignalDetectorService()
    icp_matcher = icp_matcher or LeadIcpMatcherService()
    fact_builder = fact_builder or EvidenceFactBuilder()
    scoring_engine = scoring_engine or ScoringEngine()
    scoring_config_service = scoring_config_service or ScoringConfigService()

    version = scoring_config_service.get_active_version(db, workspace_id)
    weights = ScoringWeights.model_validate(version.weights_json)
    thresholds = ScoringThresholds.model_validate(version.thresholds_json)

    evidence = evidence_repository.list_normalized_facts_for_lead(db, lead.id)
    signals = signal_detector.recompute_for_lead(
        db, workspace_id=workspace_id, lead=lead, facts=evidence
    )
    matches = icp_matcher.recompute_for_lead(
        db, workspace_id=workspace_id, lead=lead, signals=signals
    )
    best_match = max(matches, key=lambda match: match.fit_score, default=None)
    facts = fact_builder.build(lead, evidence)
    result = scoring_engine.evaluate(
        facts,
        weights=weights,
        thresholds=thresholds,
        is_qualified_candidate=True,
        icp_match=best_match,
        lead_signals=signals,
    )
    return persist_lead_score(
        db, lead_id=lead.id, scoring_config_version_id=version.id, result=result
    )
