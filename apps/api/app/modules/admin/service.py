from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.core.runtime_health import probe_ollama, probe_serpapi
from app.modules.admin.repository import AdminRepository
from app.modules.admin.schemas import (
    OperationalHealthResponse,
    PromptTemplateCreateRequest,
    PromptTemplateListResponse,
    PromptTemplateResponse,
    ProviderSettingsResponse,
    ProviderSettingsUpdateRequest,
    RecentFailedJobResponse,
    RecentProviderFailureResponse,
    ServiceCatalogItemCreateRequest,
    ServiceCatalogItemResponse,
    ServiceCatalogItemUpdateRequest,
    ServiceCatalogListResponse,
)
from app.modules.ai_analysis.models import PromptTemplate, WorkspaceServiceCatalogItem
from app.modules.ai_analysis.repository import AIAnalysisRepository
from app.modules.ai_analysis.service_catalog import ALLOWED_SERVICE_CATALOG
from app.modules.audit_logs.service import AuditLogService
from app.modules.provider_serpapi.models import ProviderFetch
from app.modules.scoring.models import ScoringConfigVersion
from app.modules.scoring.schemas import (
    ActiveScoringConfigResponse,
    ScoringConfigVersionCreateRequest,
    ScoringConfigVersionListResponse,
    ScoringConfigVersionResponse,
)
from app.modules.scoring.service import ScoringConfigService
from app.modules.search_jobs.models import SearchJob
from app.modules.users.models import User
from app.shared.enums.jobs import ProviderFetchStatus, SearchJobStatus


class AdminService:
    def __init__(self) -> None:
        self.scoring = ScoringConfigService()
        self.audit_logs = AuditLogService()
        self.ai_repository = AIAnalysisRepository()
        self.admin_repository = AdminRepository()

    def get_active_scoring(self, db: Session, *, workspace_id: int) -> ActiveScoringConfigResponse:
        version = self.scoring.get_active_version(db, workspace_id)
        creator = db.get(User, version.created_by_user_id)
        return ActiveScoringConfigResponse(
            active_version=self._to_scoring_response(version, creator)
        )

    def list_scoring_versions(
        self, db: Session, *, workspace_id: int, limit: int = 50
    ) -> ScoringConfigVersionListResponse:
        items = list(
            db.scalars(
                select(ScoringConfigVersion)
                .where(ScoringConfigVersion.workspace_id == workspace_id)
                .order_by(ScoringConfigVersion.created_at.desc())
                .limit(limit)
            )
        )
        users = self._user_lookup(db, [item.created_by_user_id for item in items])
        return ScoringConfigVersionListResponse(
            items=[
                self._to_scoring_response(item, users.get(item.created_by_user_id))
                for item in items
            ]
        )

    def create_scoring_version(
        self,
        db: Session,
        *,
        workspace_id: int,
        created_by: User,
        actor: User,
        payload: ScoringConfigVersionCreateRequest,
    ) -> ScoringConfigVersionResponse:
        version = self.scoring.create_version(
            db,
            workspace_id=workspace_id,
            created_by_user_id=created_by.id,
            weights=payload.weights,
            thresholds=payload.thresholds,
            note=payload.note,
        )
        self.audit_logs.record(
            db,
            workspace_id=workspace_id,
            actor_user_id=actor.id,
            event_name="scoring_config.created",
            details=f"Created scoring configuration version {version.public_id}.",
        )
        return self._to_scoring_response(version, created_by)

    def activate_scoring_version(
        self,
        db: Session,
        *,
        workspace_id: int,
        version_public_id: str,
        actor: User,
    ) -> ActiveScoringConfigResponse:
        version = self.admin_repository.get_scoring_version(
            db, workspace_id=workspace_id, public_id=version_public_id
        )
        if version is None:
            raise NotFoundError("Scoring configuration was not found.")
        self.scoring.activate_version(db, workspace_id=workspace_id, version=version)
        self.audit_logs.record(
            db,
            workspace_id=workspace_id,
            actor_user_id=actor.id,
            event_name="scoring_config.activated",
            details=f"Activated scoring configuration version {version.public_id}.",
        )
        creator = db.get(User, version.created_by_user_id)
        return ActiveScoringConfigResponse(
            active_version=self._to_scoring_response(version, creator)
        )

    def list_prompt_templates(
        self, db: Session, *, workspace_id: int, limit: int = 50
    ) -> PromptTemplateListResponse:
        items = self.ai_repository.list_prompt_templates(db, workspace_id, limit=limit)
        users = self._user_lookup(db, [item.created_by_user_id for item in items])
        return PromptTemplateListResponse(
            items=[
                self._to_prompt_template_response(item, users.get(item.created_by_user_id))
                for item in items
            ]
        )

    def create_prompt_template(
        self,
        db: Session,
        *,
        workspace_id: int,
        payload: PromptTemplateCreateRequest,
        actor: User,
    ) -> PromptTemplateResponse:
        template = self.ai_repository.add_prompt_template(
            db,
            PromptTemplate(
                workspace_id=workspace_id,
                name=payload.name,
                template_text=payload.template_text,
                is_active=payload.activate,
                created_by_user_id=actor.id,
            ),
        )
        if payload.activate:
            template = self.ai_repository.activate_prompt_template(
                db,
                workspace_id=workspace_id,
                template=template,
            )
        self.audit_logs.record(
            db,
            workspace_id=workspace_id,
            actor_user_id=actor.id,
            event_name="prompt_template.created",
            details=(
                f"Created prompt template {template.public_id} ({template.name})"
                + (" and activated it." if payload.activate else ".")
            ),
        )
        return self._to_prompt_template_response(template, actor)

    def activate_prompt_template(
        self,
        db: Session,
        *,
        workspace_id: int,
        prompt_template_public_id: str,
        actor: User,
    ) -> PromptTemplateResponse:
        template = self.admin_repository.get_prompt_template(
            db, workspace_id=workspace_id, public_id=prompt_template_public_id
        )
        if template is None:
            raise NotFoundError("Prompt template was not found.")
        template = self.ai_repository.activate_prompt_template(
            db,
            workspace_id=workspace_id,
            template=template,
        )
        self.audit_logs.record(
            db,
            workspace_id=workspace_id,
            actor_user_id=actor.id,
            event_name="prompt_template.activated",
            details=f"Activated prompt template {template.public_id} ({template.name}).",
        )
        return self._to_prompt_template_response(template, actor)

    def get_provider_settings(self, db: Session, *, workspace_id: int) -> ProviderSettingsResponse:
        settings = self.admin_repository.ensure_provider_settings(db, workspace_id=workspace_id)
        return ProviderSettingsResponse(
            hl=settings.hl,
            gl=settings.gl,
            google_domain=settings.google_domain,
            enrich_top_n=settings.enrich_top_n,
        )

    def update_provider_settings(
        self,
        db: Session,
        *,
        workspace_id: int,
        payload: ProviderSettingsUpdateRequest,
        actor: User,
    ) -> ProviderSettingsResponse:
        settings = self.admin_repository.ensure_provider_settings(db, workspace_id=workspace_id)
        if payload.hl is not None:
            settings.hl = payload.hl
        if payload.gl is not None:
            settings.gl = payload.gl
        if payload.google_domain is not None:
            settings.google_domain = payload.google_domain
        if payload.enrich_top_n is not None:
            settings.enrich_top_n = payload.enrich_top_n
        self.admin_repository.save_provider_settings(db, settings)
        self.audit_logs.record(
            db,
            workspace_id=workspace_id,
            actor_user_id=actor.id,
            event_name="provider_settings.updated",
            details=(
                "Updated SerpAPI workspace defaults "
                f"(hl={settings.hl}, gl={settings.gl}, domain={settings.google_domain}, enrich_top_n={settings.enrich_top_n})."
            ),
        )
        return self.get_provider_settings(db, workspace_id=workspace_id)

    def get_operational_health(
        self, db: Session, *, workspace_id: int
    ) -> OperationalHealthResponse:
        since = datetime.now(tz=UTC) - timedelta(days=7)
        failed_jobs = list(
            db.scalars(
                select(SearchJob)
                .where(
                    SearchJob.workspace_id == workspace_id,
                    SearchJob.status.in_(
                        [
                            SearchJobStatus.FAILED.value,
                            SearchJobStatus.PARTIALLY_COMPLETED.value,
                        ]
                    ),
                )
                .order_by(
                    SearchJob.finished_at.is_(None),
                    SearchJob.finished_at.desc(),
                    SearchJob.id.desc(),
                )
                .limit(10)
            )
        )
        provider_failures = list(
            db.scalars(
                select(ProviderFetch)
                .where(
                    ProviderFetch.workspace_id == workspace_id,
                    or_(
                        ProviderFetch.status != ProviderFetchStatus.OK.value,
                        ProviderFetch.error_message.is_not(None),
                    ),
                )
                .order_by(ProviderFetch.started_at.desc(), ProviderFetch.id.desc())
                .limit(10)
            )
        )
        failed_jobs_last_7_days = int(
            db.scalar(
                select(func.count(SearchJob.id)).where(
                    SearchJob.workspace_id == workspace_id,
                    SearchJob.queued_at >= since,
                    SearchJob.status.in_(
                        [
                            SearchJobStatus.FAILED.value,
                            SearchJobStatus.PARTIALLY_COMPLETED.value,
                        ]
                    ),
                )
            )
            or 0
        )
        provider_failures_last_7_days = int(
            db.scalar(
                select(func.count(ProviderFetch.id)).where(
                    ProviderFetch.workspace_id == workspace_id,
                    ProviderFetch.started_at >= since,
                    or_(
                        ProviderFetch.status != ProviderFetchStatus.OK.value,
                        ProviderFetch.error_message.is_not(None),
                    ),
                )
            )
            or 0
        )
        settings = get_settings()
        serpapi_probe = probe_serpapi(settings)
        ollama_probe = probe_ollama(settings)
        return OperationalHealthResponse(
            database_ok=bool(db.execute(text("SELECT 1")).scalar()),
            serpapi_configured=settings.has_serpapi_configured,
            serpapi_live_reachable=serpapi_probe.reachable,
            serpapi_runtime_mode=settings.serpapi_runtime_mode,
            discovery_runtime=settings.discovery_runtime,
            discovery_execution_mode=settings.effective_discovery_mode,
            discovery_kill_switch=settings.discovery_kill_switch,
            discovery_multi_engine_enabled=settings.discovery_multi_engine_enabled,
            current_ai_runtime=settings.analysis_runtime,
            analysis_runtime=settings.analysis_runtime,
            analysis_fallback_runtime=settings.analysis_fallback_runtime,
            ollama_configured=settings.has_ollama_configured,
            ollama_reachable=ollama_probe.reachable,
            openai_configured=settings.has_openai_configured,
            openai_fallback_configured=(
                settings.analysis_runtime == "ollama" and settings.has_openai_configured
            ),
            demo_fallbacks_enabled=settings.allow_demo_fallbacks,
            runtime_warnings=settings.runtime_warnings,
            failed_jobs_last_7_days=failed_jobs_last_7_days,
            provider_failures_last_7_days=provider_failures_last_7_days,
            recent_failed_jobs=[
                RecentFailedJobResponse(
                    public_id=item.public_id,
                    business_type=item.business_type,
                    city=item.city,
                    status=SearchJobStatus(item.status),
                    queued_at=item.queued_at,
                    finished_at=item.finished_at,
                    provider_error_count=item.provider_error_count,
                )
                for item in failed_jobs
            ],
            recent_provider_failures=[
                RecentProviderFailureResponse(
                    public_id=item.public_id,
                    engine=item.engine,
                    mode=item.mode,
                    status=item.status,
                    http_status=item.http_status,
                    error_message=item.error_message,
                    started_at=item.started_at,
                    finished_at=item.finished_at,
                )
                for item in provider_failures
            ],
        )

    def list_service_catalog(
        self, db: Session, *, workspace_id: int
    ) -> ServiceCatalogListResponse:
        items = self.admin_repository.list_service_catalog(db, workspace_id=workspace_id)
        if not items:
            return ServiceCatalogListResponse(
                items=[
                    ServiceCatalogItemResponse(
                        public_id=f"default_{i}",
                        service_name=name,
                        description=None,
                        is_active=True,
                        rank_order=i,
                        created_at=datetime.now(tz=UTC),
                    )
                    for i, name in enumerate(ALLOWED_SERVICE_CATALOG, start=1)
                ],
                is_default=True,
            )
        return ServiceCatalogListResponse(
            items=[self._to_catalog_response(item) for item in items],
            is_default=False,
        )

    def create_catalog_item(
        self,
        db: Session,
        *,
        workspace_id: int,
        payload: ServiceCatalogItemCreateRequest,
        actor: User,
    ) -> ServiceCatalogItemResponse:
        item = self.admin_repository.add_catalog_item(
            db,
            WorkspaceServiceCatalogItem(
                workspace_id=workspace_id,
                service_name=payload.service_name,
                description=payload.description,
                is_active=payload.is_active,
                rank_order=payload.rank_order,
            ),
        )
        self.audit_logs.record(
            db,
            workspace_id=workspace_id,
            actor_user_id=actor.id,
            event_name="service_catalog.created",
            details=f"Created service catalog item {item.public_id} ({item.service_name}).",
        )
        return self._to_catalog_response(item)

    def update_catalog_item(
        self,
        db: Session,
        *,
        workspace_id: int,
        public_id: str,
        payload: ServiceCatalogItemUpdateRequest,
        actor: User,
    ) -> ServiceCatalogItemResponse:
        item = self.admin_repository.get_catalog_item(
            db, workspace_id=workspace_id, public_id=public_id
        )
        if item is None:
            raise NotFoundError("Service catalog item was not found.")
        if payload.description is not None:
            item.description = payload.description
        if payload.is_active is not None:
            item.is_active = payload.is_active
        if payload.rank_order is not None:
            item.rank_order = payload.rank_order
        item.updated_at = datetime.now(tz=UTC)
        saved = self.admin_repository.save_catalog_item(db, item)
        return self._to_catalog_response(saved)

    def delete_catalog_item(
        self,
        db: Session,
        *,
        workspace_id: int,
        public_id: str,
        actor: User,
    ) -> None:
        item = self.admin_repository.get_catalog_item(
            db, workspace_id=workspace_id, public_id=public_id
        )
        if item is None:
            raise NotFoundError("Service catalog item was not found.")
        self.admin_repository.delete_catalog_item(db, item)
        self.audit_logs.record(
            db,
            workspace_id=workspace_id,
            actor_user_id=actor.id,
            event_name="service_catalog.deleted",
            details=f"Deleted service catalog item ({item.service_name}).",
        )

    def _to_catalog_response(
        self, item: WorkspaceServiceCatalogItem
    ) -> ServiceCatalogItemResponse:
        return ServiceCatalogItemResponse(
            public_id=item.public_id,
            service_name=item.service_name,
            description=item.description,
            is_active=item.is_active,
            rank_order=item.rank_order,
            created_at=item.created_at,
        )

    def _to_scoring_response(
        self, version: ScoringConfigVersion, creator: User | None
    ) -> ScoringConfigVersionResponse:
        from app.modules.scoring.schemas import ScoringThresholds, ScoringWeights

        return ScoringConfigVersionResponse(
            public_id=version.public_id,
            weights=ScoringWeights.model_validate(version.weights_json),
            thresholds=ScoringThresholds.model_validate(version.thresholds_json),
            note=version.note,
            created_at=version.created_at,
            created_by_user_public_id=creator.public_id if creator else "unknown",
        )

    def _to_prompt_template_response(
        self,
        template: PromptTemplate,
        creator: User | None,
    ) -> PromptTemplateResponse:
        return PromptTemplateResponse(
            public_id=template.public_id,
            name=template.name,
            template_text=template.template_text,
            is_active=template.is_active,
            created_at=template.created_at,
            created_by_user_public_id=creator.public_id if creator else "unknown",
        )

    def _user_lookup(self, db: Session, user_ids: list[int]) -> dict[int, User]:
        ids = sorted(set(user_ids))
        if not ids:
            return {}
        items = list(db.scalars(select(User).where(User.id.in_(ids))))
        return {item.id: item for item in items}
