from __future__ import annotations

import hashlib
import json

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import FeatureNotReadyError, NotFoundError
from app.modules.ai_analysis.adapters import (
    DeterministicLLMAdapter,
    FallbackAnalysisBuilder,
    LLMClient,
)
from app.modules.ai_analysis.models import AIAnalysisSnapshot, ServiceRecommendation
from app.modules.ai_analysis.prompt_builder import PromptBuilder
from app.modules.ai_analysis.repository import AIAnalysisRepository
from app.modules.ai_analysis.schemas import (
    LatestLeadAnalysisResponse,
    LeadAnalysisInput,
    LeadAnalysisResult,
    LeadAnalysisSnapshotResponse,
    LeadScoreContext,
    ServiceRecommendationResponse,
)
from app.modules.ai_analysis.service_catalog import ALLOWED_SERVICE_CATALOG
from app.modules.ai_analysis.validator import LLMOutputValidator
from app.modules.audit_logs.service import AuditLogService
from app.modules.leads.models import Lead
from app.modules.leads.repository import LeadsRepository
from app.modules.provider_serpapi.repository import ProviderEvidenceRepository
from app.modules.scoring.fact_builder import EvidenceFactBuilder
from app.modules.scoring.repository import ScoringRepository
from app.modules.users.models import User
from app.shared.dto.lead_facts import NormalizedLeadFacts


class AIAnalysisService:
    def __init__(
        self,
        *,
        llm_client: LLMClient | None = None,
        fallback_client: LLMClient | None = None,
    ) -> None:
        self.repository = AIAnalysisRepository()
        self.prompt_builder = PromptBuilder()
        self.validator = LLMOutputValidator()
        self.leads_repository = LeadsRepository()
        self.evidence_repository = ProviderEvidenceRepository()
        self.fact_builder = EvidenceFactBuilder()
        self.scoring_repository = ScoringRepository()
        self.audit_logs = AuditLogService()
        self.llm_client = llm_client
        self.fallback_client = fallback_client or FallbackAnalysisBuilder()

    def analyze(
        self,
        db: Session,
        *,
        workspace_id: int,
        lead: Lead,
        facts: NormalizedLeadFacts,
        created_by_user_id: int,
        score_context: LeadScoreContext | None = None,
    ) -> tuple[AIAnalysisSnapshot, LeadAnalysisResult]:
        adapter, provider_name, model_name = self._resolve_runtime()
        template = self.repository.get_active_prompt_template(db, workspace_id)
        if template is None:
            raise NotFoundError("Active prompt template was not found for this workspace.")

        input_payload = self.prompt_builder.build_input_payload(
            facts,
            score_context=score_context,
            allowed_service_catalog=list(ALLOWED_SERVICE_CATALOG),
        )
        prompt = self.prompt_builder.build_prompt(input_payload)
        input_hash = self._input_hash(
            prompt=prompt,
            facts=facts,
            score_context=score_context,
            prompt_template_id=template.id,
        )
        existing = self.repository.get_snapshot_by_input_hash(
            db,
            lead_id=lead.id,
            prompt_template_id=template.id,
            input_hash=input_hash,
        )
        if existing is not None:
            return existing, LeadAnalysisResult.model_validate(existing.output_json)

        result = self._run_analysis(adapter=adapter, input_payload=input_payload)
        snapshot = self.repository.add_snapshot(
            db,
            AIAnalysisSnapshot(
                lead_id=lead.id,
                prompt_template_id=template.id,
                ai_provider=provider_name,
                model_name=model_name,
                input_hash=input_hash,
                output_json=result.model_dump(),
                created_by_user_id=created_by_user_id,
            ),
        )
        self.repository.add_service_recommendations(
            db,
            [
                ServiceRecommendation(
                    lead_id=lead.id,
                    ai_analysis_snapshot_id=snapshot.id,
                    service_name=service_name,
                    rationale=None,
                    confidence=result.confidence,
                    rank_order=index,
                    created_by_user_id=created_by_user_id,
                )
                for index, service_name in enumerate(result.recommended_services, start=1)
            ],
        )
        return snapshot, result

    def get_latest_for_lead(
        self,
        db: Session,
        *,
        workspace_id: int,
        lead_public_id: str,
    ) -> LatestLeadAnalysisResponse:
        lead = self._get_lead_or_raise(db, workspace_id=workspace_id, lead_public_id=lead_public_id)
        snapshot = self.repository.get_latest_snapshot_for_lead(db, lead_id=lead.id)
        if snapshot is None:
            return LatestLeadAnalysisResponse(lead_id=lead.public_id, snapshot=None)
        result = LeadAnalysisResult.model_validate(snapshot.output_json)
        return LatestLeadAnalysisResponse(
            lead_id=lead.public_id,
            snapshot=self._to_snapshot_response(
                db,
                lead_public_id=lead.public_id,
                snapshot=snapshot,
                result=result,
            ),
        )

    def generate_for_lead(
        self,
        db: Session,
        *,
        workspace_id: int,
        lead_public_id: str,
        current_user: User,
    ) -> LeadAnalysisSnapshotResponse:
        lead, snapshot, result = self.prepare_analysis_for_lead(
            db,
            workspace_id=workspace_id,
            lead_public_id=lead_public_id,
            created_by_user_id=current_user.id,
        )
        self.audit_logs.record(
            db,
            workspace_id=workspace_id,
            actor_user_id=current_user.id,
            event_name="lead.analyzed",
            details=f"Generated an assistive analysis for lead {lead.public_id}.",
        )
        return self._to_snapshot_response(
            db,
            lead_public_id=lead.public_id,
            snapshot=snapshot,
            result=result,
        )

    def prepare_analysis_for_lead(
        self,
        db: Session,
        *,
        workspace_id: int,
        lead_public_id: str,
        created_by_user_id: int,
    ) -> tuple[Lead, AIAnalysisSnapshot, LeadAnalysisResult]:
        lead = self._get_lead_or_raise(db, workspace_id=workspace_id, lead_public_id=lead_public_id)
        facts = self._facts_from_lead(db, lead)
        score_context = self._score_context(db, lead.id)
        snapshot, result = self.analyze(
            db,
            workspace_id=workspace_id,
            lead=lead,
            facts=facts,
            created_by_user_id=created_by_user_id,
            score_context=score_context,
        )
        return lead, snapshot, result

    def _resolve_runtime(self) -> tuple[LLMClient, str, str]:
        if self.llm_client is not None:
            return self.llm_client, "custom", "custom-client"
        settings = get_settings()
        if settings.ai_provider != "stub":
            raise FeatureNotReadyError(
                f"Unsupported ai_provider '{settings.ai_provider}'. Only 'stub' is enabled in this build."
            )
        return DeterministicLLMAdapter(), "stub", "deterministic-rules-v1"

    def _run_analysis(
        self,
        *,
        adapter: LLMClient,
        input_payload: LeadAnalysisInput,
    ) -> LeadAnalysisResult:
        try:
            payload = adapter.analyze(input_payload)
            return self.validator.validate(payload)
        except Exception:
            fallback_payload = self.fallback_client.analyze(input_payload)
            return self.validator.validate(fallback_payload)

    def _input_hash(
        self,
        *,
        prompt: str,
        facts: NormalizedLeadFacts,
        score_context: LeadScoreContext | None,
        prompt_template_id: int,
    ) -> str:
        payload = {
            "prompt": prompt,
            "prompt_template_id": prompt_template_id,
            "facts": facts.model_dump(mode="json"),
            "score_context": score_context.model_dump(mode="json") if score_context else None,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _get_lead_or_raise(
        self,
        db: Session,
        *,
        workspace_id: int,
        lead_public_id: str,
    ) -> Lead:
        lead = self.leads_repository.get_by_public_id(db, lead_public_id)
        if lead is None or lead.workspace_id != workspace_id:
            raise NotFoundError("Lead was not found.")
        return lead

    def _facts_from_lead(self, db: Session, lead: Lead) -> NormalizedLeadFacts:
        evidence = self.evidence_repository.list_normalized_facts_for_lead(db, lead.id)
        return self.fact_builder.build(lead, evidence)

    def _score_context(self, db: Session, lead_id: int) -> LeadScoreContext | None:
        try:
            breakdown = self.scoring_repository.get_latest_score_breakdown(db, lead_id)
        except NotFoundError:
            return None
        reasons = [
            item.reason
            for item in sorted(
                breakdown.breakdown,
                key=lambda item: abs(item.contribution),
                reverse=True,
            )[:3]
        ]
        return LeadScoreContext(
            total_score=breakdown.total_score,
            band=breakdown.band.value,
            qualified=breakdown.qualified,
            reasons=reasons,
        )

    def _to_snapshot_response(
        self,
        db: Session,
        *,
        lead_public_id: str,
        snapshot: AIAnalysisSnapshot,
        result: LeadAnalysisResult,
    ) -> LeadAnalysisSnapshotResponse:
        recommendations = self.repository.list_service_recommendations(db, snapshot_id=snapshot.id)
        return LeadAnalysisSnapshotResponse(
            public_id=snapshot.public_id,
            lead_id=lead_public_id,
            ai_provider=snapshot.ai_provider,
            model_name=snapshot.model_name,
            created_at=snapshot.created_at,
            analysis=result,
            service_recommendations=[
                ServiceRecommendationResponse(
                    public_id=item.public_id,
                    service_name=item.service_name,
                    rationale=item.rationale,
                    confidence=item.confidence,
                    rank_order=item.rank_order,
                    created_at=item.created_at,
                )
                for item in recommendations
            ],
        )
