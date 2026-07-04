from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import NotFoundError, ServiceUnavailableError
from app.modules.ai_analysis.adapters import LLMClient, OllamaLLMAdapter, OpenAILLMAdapter
from app.modules.ai_analysis.evidence_builder import EvidenceBuilder
from app.modules.ai_analysis.models import (
    AIAnalysisEvidence,
    AIAnalysisSnapshot,
    AIFeedback,
    PromptTemplate,
    ServiceRecommendation,
)
from app.modules.ai_analysis.prompt_builder import PromptBuilder
from app.modules.ai_analysis.repository import AIAnalysisRepository
from app.modules.ai_analysis.schemas import (
    AIEvidenceItem,
    AIFeedbackRequest,
    AIFeedbackResponse,
    BatchAnalysisResponse,
    BatchAnalysisResult,
    LatestLeadAnalysisResponse,
    LeadAiEvidenceResponse,
    LeadAnalysisHistoryResponse,
    LeadAnalysisInput,
    LeadAnalysisResult,
    LeadAnalysisSnapshotResponse,
    LeadScoreContext,
    ServiceRecommendationResponse,
)
from app.modules.ai_analysis.service_catalog import get_default_service_catalog
from app.modules.ai_analysis.validator import LLMOutputValidator
from app.modules.audit_logs.service import AuditLogService
from app.modules.leads.models import Lead
from app.modules.leads.repository import LeadsRepository
from app.modules.users.models import User, Workspace
from app.shared.dto.lead_facts import NormalizedLeadFacts
from app.shared.services.lead_intelligence import LeadIntelligenceService
from app.shared.utils.workspace_profile import get_workspace_profession

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RuntimeCandidate:
    adapter: LLMClient
    provider_name: str
    model_name: str


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
        self.evidence_builder = EvidenceBuilder()
        self.leads_repository = LeadsRepository()
        self.lead_intelligence = LeadIntelligenceService()
        self.audit_logs = AuditLogService()
        self.llm_client = llm_client
        self.fallback_client = fallback_client

    def analyze(
        self,
        db: Session,
        *,
        workspace_id: int,
        lead: Lead,
        facts: NormalizedLeadFacts,
        created_by_user_id: int,
        score_context: LeadScoreContext | None = None,
        force_refresh: bool = False,
    ) -> tuple[AIAnalysisSnapshot, LeadAnalysisResult]:
        runtime_candidates = self._resolve_runtime_candidates()
        template = self._get_or_create_active_prompt_template(
            db,
            workspace_id=workspace_id,
            created_by_user_id=created_by_user_id,
        )

        input_payload = self.prompt_builder.build_input_payload(
            facts,
            score_context=score_context,
            allowed_service_catalog=self._resolve_service_catalog(db, workspace_id=workspace_id),
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
        if existing is not None and not force_refresh:
            return existing, LeadAnalysisResult.model_validate(existing.output_json)

        result, provider_name, model_name = self._run_analysis(
            candidates=runtime_candidates,
            input_payload=input_payload,
        )
        # Set before add_snapshot so its commit flushes this dirty lead, regardless of
        # whether service recommendations exist (that path may skip its own commit).
        if result.summary:
            lead.ai_opener = result.summary
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
        self._persist_evidence(db, workspace_id=workspace_id, lead=lead, snapshot=snapshot)
        return snapshot, result

    def _persist_evidence(
        self,
        db: Session,
        *,
        workspace_id: int,
        lead: Lead,
        snapshot: AIAnalysisSnapshot,
    ) -> None:
        records = self.evidence_builder.build(db, workspace_id=workspace_id, lead=lead)
        if not records:
            return
        self.repository.add_evidence(
            db,
            [
                AIAnalysisEvidence(
                    workspace_id=workspace_id,
                    ai_analysis_snapshot_id=snapshot.id,
                    source_type=record.source_type,
                    source_url=record.source_url,
                    evidence_text=record.evidence_text,
                    confidence=record.confidence,
                )
                for record in records
            ],
        )

    def get_evidence_for_lead(
        self,
        db: Session,
        *,
        workspace_id: int,
        lead_public_id: str,
    ) -> LeadAiEvidenceResponse:
        lead = self._get_lead_or_raise(db, workspace_id=workspace_id, lead_public_id=lead_public_id)
        snapshot = self.repository.get_latest_snapshot_for_lead(db, lead_id=lead.id)
        if snapshot is None:
            return LeadAiEvidenceResponse(lead_id=lead.public_id, snapshot_public_id=None, items=[])
        evidence = self.repository.list_evidence_for_snapshot(db, snapshot_id=snapshot.id)
        return LeadAiEvidenceResponse(
            lead_id=lead.public_id,
            snapshot_public_id=snapshot.public_id,
            items=[
                AIEvidenceItem(
                    public_id=item.public_id,
                    source_type=item.source_type,
                    source_url=item.source_url,
                    evidence_text=item.evidence_text,
                    confidence=item.confidence,
                    created_at=item.created_at,
                )
                for item in evidence
            ],
        )

    def submit_feedback(
        self,
        db: Session,
        *,
        workspace_id: int,
        snapshot_public_id: str,
        payload: AIFeedbackRequest,
        current_user: User,
    ) -> AIFeedbackResponse:
        snapshot = self.repository.get_snapshot_by_public_id(db, snapshot_public_id)
        if snapshot is None:
            raise NotFoundError("Analysis snapshot was not found.")
        # Enforce tenant isolation: the snapshot's lead must belong to the caller's workspace.
        lead = self.leads_repository.get_by_id_for_workspace(
            db, workspace_id=workspace_id, lead_id=snapshot.lead_id
        )
        if lead is None:
            raise NotFoundError("Analysis snapshot was not found.")
        feedback = self.repository.add_feedback(
            db,
            AIFeedback(
                workspace_id=workspace_id,
                ai_analysis_snapshot_id=snapshot.id,
                user_id=current_user.id,
                rating=payload.rating,
                correction_text=payload.correction_text,
            ),
        )
        self.audit_logs.record(
            db,
            workspace_id=workspace_id,
            actor_user_id=current_user.id,
            event_name="ai_analysis.feedback_submitted",
            details=(
                f"Recorded '{payload.rating}' feedback on analysis {snapshot.public_id} "
                f"for lead {lead.public_id}."
            ),
        )
        return AIFeedbackResponse(
            public_id=feedback.public_id,
            snapshot_public_id=snapshot.public_id,
            rating=feedback.rating,
            correction_text=feedback.correction_text,
            created_at=feedback.created_at,
        )

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
            force_refresh=True,
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
        force_refresh: bool = False,
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
            force_refresh=force_refresh,
        )
        return lead, snapshot, result

    def list_history_for_lead(
        self,
        db: Session,
        *,
        workspace_id: int,
        lead_public_id: str,
    ) -> LeadAnalysisHistoryResponse:
        lead = self._get_lead_or_raise(db, workspace_id=workspace_id, lead_public_id=lead_public_id)
        snapshots = self.repository.list_snapshots_for_lead(db, lead_id=lead.id)
        items = [
            self._to_snapshot_response(
                db,
                lead_public_id=lead.public_id,
                snapshot=snap,
                result=LeadAnalysisResult.model_validate(snap.output_json),
            )
            for snap in snapshots
        ]
        return LeadAnalysisHistoryResponse(lead_id=lead.public_id, items=items)

    def generate_batch(
        self,
        db: Session,
        *,
        workspace_id: int,
        lead_public_ids: list[str],
        current_user: User,
    ) -> BatchAnalysisResponse:
        results: list[BatchAnalysisResult] = []
        for lead_public_id in lead_public_ids:
            try:
                lead, snapshot, result = self.prepare_analysis_for_lead(
                    db,
                    workspace_id=workspace_id,
                    lead_public_id=lead_public_id,
                    created_by_user_id=current_user.id,
                )
                results.append(
                    BatchAnalysisResult(
                        lead_id=lead_public_id,
                        snapshot=self._to_snapshot_response(
                            db,
                            lead_public_id=lead.public_id,
                            snapshot=snapshot,
                            result=result,
                        ),
                    )
                )
            except NotFoundError:
                results.append(BatchAnalysisResult(lead_id=lead_public_id, error="Lead not found."))
            except Exception as exc:
                results.append(BatchAnalysisResult(lead_id=lead_public_id, error=str(exc)))
        return BatchAnalysisResponse(triggered_count=len(results), results=results)

    def test_prompt_template(
        self,
        db: Session,
        *,
        workspace_id: int,
        template_public_id: str,
        lead_public_id: str,
        current_user: User,
    ) -> LeadAnalysisSnapshotResponse:
        from datetime import UTC, datetime

        from app.modules.admin.repository import AdminRepository

        template = AdminRepository().get_prompt_template(
            db, workspace_id=workspace_id, public_id=template_public_id
        )
        if template is None:
            raise NotFoundError("Prompt template was not found.")
        lead = self._get_lead_or_raise(db, workspace_id=workspace_id, lead_public_id=lead_public_id)
        context = self.lead_intelligence.build(db, lead=lead)
        input_payload = self.prompt_builder.build_input_payload(
            context.facts,
            score_context=context.score_context,
            allowed_service_catalog=self._resolve_service_catalog(db, workspace_id=workspace_id),
            prompt_instructions=template.template_text,
        )
        result, provider_name, model_name = self._run_analysis(
            candidates=self._resolve_runtime_candidates(),
            input_payload=input_payload,
        )
        return LeadAnalysisSnapshotResponse(
            public_id=f"preview_{template.public_id}",
            lead_id=lead_public_id,
            ai_provider=provider_name,
            model_name=model_name,
            created_at=datetime.now(tz=UTC),
            analysis=result,
            service_recommendations=[],
        )

    def _resolve_service_catalog(self, db: Session, *, workspace_id: int) -> list[str]:
        from app.modules.admin.repository import AdminRepository

        items = AdminRepository().list_service_catalog(db, workspace_id=workspace_id)
        active_items = [item.service_name for item in items if item.is_active]
        if active_items:
            return active_items
        workspace = db.get(Workspace, workspace_id)
        profession = get_workspace_profession(workspace)
        return list(get_default_service_catalog(profession))

    def _resolve_runtime_candidates(self) -> list[RuntimeCandidate]:
        if self.llm_client is not None:
            custom_candidates = [
                RuntimeCandidate(
                    adapter=self.llm_client,
                    provider_name="custom",
                    model_name="custom-client",
                )
            ]
            if self.fallback_client is not None:
                custom_candidates.append(
                    RuntimeCandidate(
                        adapter=self.fallback_client,
                        provider_name="custom-fallback",
                        model_name="custom-fallback-client",
                    )
                )
            return custom_candidates

        settings = get_settings()
        runtime_candidates: list[RuntimeCandidate] = []

        if settings.analysis_runtime == "demo":
            raise ServiceUnavailableError(
                "AI analysis demo mode is not available for this local-live profile. "
                "Configure Ollama as primary and OpenAI as fallback."
            )

        if settings.analysis_runtime == "ollama":
            runtime_candidates.append(
                RuntimeCandidate(
                    adapter=OllamaLLMAdapter(
                        base_url=settings.ollama_base_url,
                        model=settings.ollama_model,
                    ),
                    provider_name="ollama",
                    model_name=settings.ollama_model,
                )
            )
            if settings.analysis_fallback_runtime == "openai":
                runtime_candidates.append(
                    RuntimeCandidate(
                        adapter=OpenAILLMAdapter(
                            api_key=settings.openai_api_key,
                            model=settings.openai_model,
                            base_url=settings.openai_base_url,
                        ),
                        provider_name="openai",
                        model_name=settings.openai_model,
                    )
                )
            return runtime_candidates

        if settings.analysis_runtime == "openai":
            runtime_candidates.append(
                RuntimeCandidate(
                    adapter=OpenAILLMAdapter(
                        api_key=settings.openai_api_key,
                        model=settings.openai_model,
                        base_url=settings.openai_base_url,
                    ),
                    provider_name="openai",
                    model_name=settings.openai_model,
                )
            )
            if settings.analysis_fallback_runtime == "ollama":
                runtime_candidates.append(
                    RuntimeCandidate(
                        adapter=OllamaLLMAdapter(
                            base_url=settings.ollama_base_url,
                            model=settings.ollama_model,
                        ),
                        provider_name="ollama",
                        model_name=settings.ollama_model,
                    )
                )
            return runtime_candidates

        raise ServiceUnavailableError(
            detail="AI analysis is unavailable because no LLM provider is configured. "
            "Please configure Ollama as primary or OpenAI as fallback."
        )

    def _run_analysis(
        self,
        *,
        candidates: list[RuntimeCandidate],
        input_payload: LeadAnalysisInput,
    ) -> tuple[LeadAnalysisResult, str, str]:
        last_error: Exception | None = None
        for candidate in candidates:
            try:
                payload = candidate.adapter.analyze(input_payload)
                return (
                    self.validator.validate(payload),
                    candidate.provider_name,
                    candidate.model_name,
                )
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "ai_analysis.adapter_failed provider=%s model=%s -- trying next runtime if available",
                    candidate.provider_name,
                    candidate.model_name,
                    exc_info=True,
                )

        detail = "AI analysis failed because all configured providers were unavailable or returned invalid output."
        if last_error is not None:
            detail += f" Last error: {last_error}"
        raise ServiceUnavailableError(detail)

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
                "Do not invent unsupported facts. Keep recommendations tied to the allowed service catalog. "
                "Return every user-facing generated text in both Arabic and English."
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
