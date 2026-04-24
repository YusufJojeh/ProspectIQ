from __future__ import annotations

import hashlib
import json
import logging

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.core.config import get_settings
from app.core.errors import NotFoundError, ServiceUnavailableError
from app.modules.ai_analysis.adapters import (
    DeterministicLLMAdapter,
    FallbackAnalysisBuilder,
    LLMClient,
    OllamaLLMAdapter,
    OpenAILLMAdapter,
)
from app.modules.ai_analysis.models import AIAnalysisSnapshot, PromptTemplate, ServiceRecommendation
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
from app.modules.users.models import User
from app.shared.dto.lead_facts import NormalizedLeadFacts
from app.shared.services.lead_intelligence import LeadIntelligenceService


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
        self.lead_intelligence = LeadIntelligenceService()
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
        template = self._get_or_create_active_prompt_template(
            db,
            workspace_id=workspace_id,
            created_by_user_id=created_by_user_id,
        )

        input_payload = self.prompt_builder.build_input_payload(
            facts,
            score_context=score_context,
            allowed_service_catalog=list(ALLOWED_SERVICE_CATALOG),
            prompt_instructions=template.template_text,
        )
        prompt = self.prompt_builder.build_prompt(input_payload)
        input_hash = self._input_hash(
            prompt=prompt,
            facts=facts,
            score_context=score_context,
            prompt_template_id=template.id,
            prompt_template_text=template.template_text,
        )
        existing = self.repository.get_snapshot_by_input_hash(
            db,
            lead_id=lead.id,
            prompt_template_id=template.id,
            input_hash=input_hash,
        )
        if existing is not None:
            return existing, LeadAnalysisResult.model_validate(existing.output_json)

        result, provider_name, model_name = self._run_analysis(
            adapter=adapter,
            input_payload=input_payload,
            provider_name=provider_name,
            model_name=model_name,
        )
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
        context = self.lead_intelligence.build(db, lead=lead)
        snapshot, result = self.analyze(
            db,
            workspace_id=workspace_id,
            lead=lead,
            facts=context.facts,
            created_by_user_id=created_by_user_id,
            score_context=context.score_context,
        )
        return lead, snapshot, result

    def _resolve_runtime(self) -> tuple[LLMClient, str, str]:
        if self.llm_client is not None:
            return self.llm_client, "custom", "custom-client"
        settings = get_settings()
        provider = settings.ai_provider.strip().casefold()
        if provider in {"stub", "demo"}:
            return DeterministicLLMAdapter(), "demo", "deterministic-rules-v1"
        if provider == "openai":
            if settings.has_openai_configured:
                return (
                    OpenAILLMAdapter(
                        api_key=settings.openai_api_key,
                        model=settings.openai_model,
                    ),
                    "openai",
                    settings.openai_model,
                )
            if settings.allow_demo_fallbacks:
                return DeterministicLLMAdapter(), "demo-fallback", "deterministic-rules-v1"
            raise ServiceUnavailableError(
                "AI analysis is unavailable because OPENAI_API_KEY is not configured and demo fallbacks are disabled."
            )
        if provider == "ollama":
            if settings.ollama_base_url.strip() and settings.ollama_model.strip():
                return (
                    OllamaLLMAdapter(
                        base_url=settings.ollama_base_url,
                        model=settings.ollama_model,
                    ),
                    "ollama",
                    settings.ollama_model,
                )
            if settings.allow_demo_fallbacks:
                return DeterministicLLMAdapter(), "demo-fallback", "deterministic-rules-v1"
            raise ServiceUnavailableError(
                "AI analysis is unavailable because the Ollama runtime is not configured and demo fallbacks are disabled."
            )
        if settings.allow_demo_fallbacks:
            return DeterministicLLMAdapter(), "demo-fallback", "deterministic-rules-v1"
        raise ServiceUnavailableError(
            f"AI analysis is unavailable because ai_provider '{settings.ai_provider}' is unsupported."
        )

    def _run_analysis(
        self,
        *,
        adapter: LLMClient,
        input_payload: LeadAnalysisInput,
        provider_name: str,
        model_name: str,
    ) -> tuple[LeadAnalysisResult, str, str]:
        try:
            payload = adapter.analyze(input_payload)
            return self.validator.validate(payload), provider_name, model_name
        except Exception:
            logger.warning(
                "ai_analysis.adapter_failed provider=%s model=%s — falling back to deterministic builder",
                provider_name,
                model_name,
                exc_info=True,
            )
            fallback_payload = self.fallback_client.analyze(input_payload)
            return (
                self.validator.validate(fallback_payload),
                "demo-fallback",
                "fallback-builder-v1",
            )

    def _input_hash(
        self,
        *,
        prompt: str,
        facts: NormalizedLeadFacts,
        score_context: LeadScoreContext | None,
        prompt_template_id: int,
        prompt_template_text: str,
    ) -> str:
        payload = {
            "prompt": prompt,
            "prompt_template_id": prompt_template_id,
            "prompt_template_text": prompt_template_text,
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
        lead = self.leads_repository.get_by_public_id_for_workspace(
            db,
            workspace_id=workspace_id,
            public_id=lead_public_id,
        )
        if lead is None:
            raise NotFoundError("Lead was not found.")
        return lead

    def _get_or_create_active_prompt_template(
        self,
        db: Session,
        *,
        workspace_id: int,
        created_by_user_id: int,
    ) -> PromptTemplate:
        template = self.repository.get_active_prompt_template(db, workspace_id)
        if template is not None:
            return template
        default_template = PromptTemplate(
            workspace_id=workspace_id,
            name="Default evidence-first prompt",
            template_text=(
                "Use only the stored evidence and deterministic score context. "
                "Do not invent unsupported facts. Keep recommendations tied to the allowed service catalog."
            ),
            is_active=True,
            created_by_user_id=created_by_user_id,
        )
        template = self.repository.add_prompt_template(db, default_template)
        return self.repository.activate_prompt_template(
            db,
            workspace_id=workspace_id,
            template=template,
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
