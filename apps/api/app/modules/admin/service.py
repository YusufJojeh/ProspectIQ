from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.core.runtime_health import probe_ollama, probe_serpapi
from app.modules.admin.repository import AdminRepository
from app.modules.admin.schemas import (
    AdminActionResponse,
    AdminAIFeedbackResponse,
    AdminAIFeedbackSummaryResponse,
    AdminAIUsageResponse,
    AdminAuditLogResponse,
    AdminFeatureHealthResponse,
    AdminFlaggedAnalysisResponse,
    AdminInvoiceItemResponse,
    AdminInvoiceListResponse,
    AdminInvoiceResponse,
    AdminPaymentAttemptResponse,
    AdminPlanListResponse,
    AdminPlanResponse,
    AdminProviderFetchResponse,
    AdminProviderSettingResponse,
    AdminProvidersResponse,
    AdminSearchJobListResponse,
    AdminSearchJobResponse,
    AdminSubscriptionListResponse,
    AdminSubscriptionResponse,
    AdminUsageCounterResponse,
    AdminUsageListResponse,
    AdminUsageMetricResponse,
    AdminUserListResponse,
    AdminUserSummaryResponse,
    AdminWorkspaceDetailResponse,
    AdminWorkspaceListResponse,
    AdminWorkspaceSummaryResponse,
    OperationalHealthResponse,
    PlatformAdminOverviewResponse,
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
from app.modules.ai_analysis.models import (
    AIAnalysisEvidence,
    AIAnalysisSnapshot,
    AIFeedback,
    PromptTemplate,
    WorkspaceServiceCatalogItem,
)
from app.modules.ai_analysis.repository import AIAnalysisRepository
from app.modules.ai_analysis.service_catalog import get_default_service_catalog
from app.modules.audit_logs.models import AuditLog
from app.modules.audit_logs.service import AuditLogService
from app.modules.billing.models import (
    Invoice,
    InvoiceItem,
    PaymentAttempt,
    Plan,
    Subscription,
    UsageCounter,
)
from app.modules.icp.models import IcpProfile
from app.modules.leads.models import Lead
from app.modules.provider_serpapi.models import ProviderFetch, ProviderSettings
from app.modules.scoring.models import LeadScore, ScoringConfigVersion
from app.modules.scoring.schemas import (
    ActiveScoringConfigResponse,
    ScoringConfigVersionCreateRequest,
    ScoringConfigVersionListResponse,
    ScoringConfigVersionResponse,
)
from app.modules.scoring.service import ScoringConfigService
from app.modules.search_jobs.models import SearchJob
from app.modules.signals.models import LeadSignal
from app.modules.users.models import User, Workspace
from app.shared.enums.jobs import ProviderFetchStatus, SearchJobStatus
from app.shared.utils.workspace_profile import get_workspace_profession


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

    def list_service_catalog(self, db: Session, *, workspace_id: int) -> ServiceCatalogListResponse:
        items = self.admin_repository.list_service_catalog(db, workspace_id=workspace_id)
        if not items:
            workspace = db.get(Workspace, workspace_id)
            profession = get_workspace_profession(workspace)
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
                    for i, name in enumerate(get_default_service_catalog(profession), start=1)
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

    def get_platform_overview(self, db: Session) -> PlatformAdminOverviewResponse:
        usage_rows = db.execute(
            select(UsageCounter.metric_key, func.coalesce(func.sum(UsageCounter.current_value), 0))
            .group_by(UsageCounter.metric_key)
            .order_by(UsageCounter.metric_key.asc())
        ).all()
        provider_error_count = self._count(
            db,
            select(func.count(ProviderFetch.id)).where(
                or_(
                    ProviderFetch.status != ProviderFetchStatus.OK.value,
                    ProviderFetch.error_message.is_not(None),
                )
            ),
        )
        return PlatformAdminOverviewResponse(
            total_workspaces=self._count(db, select(func.count(Workspace.id))),
            active_workspaces=self._count(
                db, select(func.count(Workspace.id)).where(Workspace.status == "active")
            ),
            disabled_workspaces=self._count(
                db,
                select(func.count(Workspace.id)).where(
                    Workspace.status.in_(["disabled", "suspended"])
                ),
            ),
            total_users=self._count(db, select(func.count(User.id))),
            active_users=self._count(
                db, select(func.count(User.id)).where(User.status == "active")
            ),
            total_leads=self._count(db, select(func.count(Lead.id))),
            total_search_jobs=self._count(db, select(func.count(SearchJob.id))),
            failed_search_jobs=self._count(
                db, select(func.count(SearchJob.id)).where(SearchJob.status == "failed")
            ),
            total_ai_analyses=self._count(db, select(func.count(AIAnalysisSnapshot.id))),
            total_evidence_rows=self._count(db, select(func.count(AIAnalysisEvidence.id))),
            total_icp_profiles=self._count(db, select(func.count(IcpProfile.id))),
            total_signals=self._count(db, select(func.count(LeadSignal.id))),
            monthly_recurring_revenue=self._monthly_recurring_revenue(db),
            unpaid_invoices_count=self._count(
                db,
                select(func.count(Invoice.id)).where(Invoice.status.in_(["open", "past_due"])),
            ),
            provider_error_count=provider_error_count,
            usage_by_metric=[
                AdminUsageMetricResponse(metric_key=str(metric), current_value=int(value or 0))
                for metric, value in usage_rows
            ],
        )

    def list_platform_workspaces(self, db: Session) -> AdminWorkspaceListResponse:
        workspaces = list(db.scalars(select(Workspace).order_by(Workspace.created_at.desc())))
        return AdminWorkspaceListResponse(
            items=[self._workspace_summary(db, workspace) for workspace in workspaces]
        )

    def get_platform_workspace_detail(
        self, db: Session, *, workspace_public_id: str
    ) -> AdminWorkspaceDetailResponse:
        workspace = self._get_workspace_or_404(db, workspace_public_id)
        summary = self._workspace_summary(db, workspace)
        owner = db.get(User, workspace.owner_user_id) if workspace.owner_user_id else None
        return AdminWorkspaceDetailResponse(
            workspace=summary,
            owner=self._user_summary(db, owner) if owner else None,
            users=self._workspace_users(db, workspace.id),
            users_count=summary.users_count,
            leads_count=summary.leads_count,
            searches_count=self._count(
                db,
                select(func.count(SearchJob.id)).where(SearchJob.workspace_id == workspace.id),
            ),
            icp_profiles_count=self._count(
                db,
                select(func.count(IcpProfile.id)).where(IcpProfile.workspace_id == workspace.id),
            ),
            signals_count=self._count(
                db,
                select(func.count(LeadSignal.id)).where(LeadSignal.workspace_id == workspace.id),
            ),
            scoring_versions_count=self._count(
                db,
                select(func.count(ScoringConfigVersion.id)).where(
                    ScoringConfigVersion.workspace_id == workspace.id
                ),
            ),
            lead_scores_count=self._workspace_lead_score_count(db, workspace.id),
            ai_analyses_count=self._workspace_ai_analysis_count(db, workspace.id),
            ai_evidence_count=self._count(
                db,
                select(func.count(AIAnalysisEvidence.id)).where(
                    AIAnalysisEvidence.workspace_id == workspace.id
                ),
            ),
            ai_feedback_count=self._count(
                db,
                select(func.count(AIFeedback.id)).where(AIFeedback.workspace_id == workspace.id),
            ),
            subscription=self._workspace_subscription(db, workspace),
            invoices=self._workspace_invoices(db, workspace, limit=10),
            usage_counters=self._workspace_usage(db, workspace),
            recent_jobs=self._workspace_jobs(db, workspace, limit=10),
            recent_provider_errors=self._workspace_provider_errors(db, workspace, limit=10),
            recent_audit_logs=self._workspace_audit_logs(db, workspace.id, limit=10),
        )

    def set_workspace_enabled(
        self,
        db: Session,
        *,
        workspace_public_id: str,
        enabled: bool,
        actor: User,
    ) -> AdminActionResponse:
        workspace = self._get_workspace_or_404(db, workspace_public_id)
        workspace.status = "active" if enabled else "disabled"
        workspace.updated_at = datetime.now(tz=UTC)
        db.add(workspace)
        db.commit()
        self.audit_logs.record(
            db,
            workspace_id=workspace.id,
            actor_user_id=actor.id,
            event_name="platform_admin.workspace_enabled"
            if enabled
            else "platform_admin.workspace_disabled",
            details=(
                f"Platform admin {actor.public_id} "
                f"{'enabled' if enabled else 'disabled'} workspace {workspace.public_id}."
            ),
        )
        return AdminActionResponse(status=workspace.status)

    def list_platform_users(self, db: Session) -> AdminUserListResponse:
        rows = db.execute(
            select(User)
            .join(Workspace, Workspace.id == User.workspace_id)
            .order_by(User.created_at.desc(), User.id.desc())
        ).scalars()
        return AdminUserListResponse(items=[self._user_summary(db, user) for user in rows])

    def set_user_enabled(
        self,
        db: Session,
        *,
        user_public_id: str,
        enabled: bool,
        actor: User,
    ) -> AdminActionResponse:
        user = db.scalar(select(User).where(User.public_id == user_public_id))
        if user is None:
            raise NotFoundError("User was not found.")
        user.status = "active" if enabled else "inactive"
        user.updated_at = datetime.now(tz=UTC)
        db.add(user)
        db.commit()
        self.audit_logs.record(
            db,
            workspace_id=user.workspace_id,
            actor_user_id=actor.id,
            event_name="platform_admin.user_enabled"
            if enabled
            else "platform_admin.user_disabled",
            details=(
                f"Platform admin {actor.public_id} "
                f"{'enabled' if enabled else 'disabled'} user {user.public_id} ({user.email})."
            ),
        )
        return AdminActionResponse(status=user.status)

    def list_platform_plans(self, db: Session) -> AdminPlanListResponse:
        plans = list(db.scalars(select(Plan).order_by(Plan.monthly_price.asc(), Plan.id.asc())))
        return AdminPlanListResponse(
            items=[
                AdminPlanResponse(
                    code=plan.code,
                    name=plan.name,
                    monthly_price=float(plan.monthly_price),
                    yearly_price=float(plan.yearly_price),
                    limits={str(key): int(value) for key, value in plan.limits_json.items()},
                    is_active=plan.is_active,
                )
                for plan in plans
            ]
        )

    def list_platform_subscriptions(self, db: Session) -> AdminSubscriptionListResponse:
        rows = db.execute(
            select(Subscription, Plan, Workspace)
            .join(Plan, Plan.id == Subscription.plan_id)
            .join(Workspace, Workspace.id == Subscription.workspace_id)
            .order_by(Subscription.created_at.desc(), Subscription.id.desc())
        ).all()
        return AdminSubscriptionListResponse(
            items=[
                self._subscription_response(subscription, plan, workspace)
                for subscription, plan, workspace in rows
            ]
        )

    def list_platform_invoices(self, db: Session) -> AdminInvoiceListResponse:
        return AdminInvoiceListResponse(items=self._invoice_rows(db, limit=100))

    def list_platform_usage(self, db: Session) -> AdminUsageListResponse:
        rows = db.execute(
            select(UsageCounter, Workspace)
            .join(Workspace, Workspace.id == UsageCounter.workspace_id)
            .order_by(UsageCounter.period_end.desc(), UsageCounter.metric_key.asc())
        ).all()
        return AdminUsageListResponse(
            items=[
                AdminUsageCounterResponse(
                    workspace_public_id=workspace.public_id,
                    workspace_name=workspace.name,
                    metric_key=counter.metric_key,
                    current_value=counter.current_value,
                    period_start=counter.period_start,
                    period_end=counter.period_end,
                )
                for counter, workspace in rows
            ]
        )

    def get_platform_providers(self, db: Session) -> AdminProvidersResponse:
        settings_rows = db.execute(
            select(ProviderSettings, Workspace)
            .join(Workspace, Workspace.id == ProviderSettings.workspace_id)
            .order_by(Workspace.name.asc())
        ).all()
        fetch_rows = db.execute(
            select(ProviderFetch, Workspace)
            .join(Workspace, Workspace.id == ProviderFetch.workspace_id)
            .order_by(ProviderFetch.started_at.desc(), ProviderFetch.id.desc())
            .limit(50)
        ).all()
        failure_filter = or_(
            ProviderFetch.status != ProviderFetchStatus.OK.value,
            ProviderFetch.error_message.is_not(None),
        )
        error_rows = db.execute(
            select(ProviderFetch, Workspace)
            .join(Workspace, Workspace.id == ProviderFetch.workspace_id)
            .where(failure_filter)
            .order_by(ProviderFetch.started_at.desc(), ProviderFetch.id.desc())
            .limit(20)
        ).all()
        return AdminProvidersResponse(
            settings=[
                AdminProviderSettingResponse(
                    workspace_public_id=workspace.public_id,
                    workspace_name=workspace.name,
                    hl=settings.hl,
                    gl=settings.gl,
                    google_domain=settings.google_domain,
                    enrich_top_n=settings.enrich_top_n,
                )
                for settings, workspace in settings_rows
            ],
            recent_fetches=[
                self._provider_fetch_response(fetch, workspace) for fetch, workspace in fetch_rows
            ],
            recent_errors=[
                self._provider_fetch_response(fetch, workspace) for fetch, workspace in error_rows
            ],
            success_count=self._count(
                db,
                select(func.count(ProviderFetch.id)).where(
                    ProviderFetch.status == ProviderFetchStatus.OK.value,
                    ProviderFetch.error_message.is_(None),
                ),
            ),
            failure_count=self._count(
                db, select(func.count(ProviderFetch.id)).where(failure_filter)
            ),
        )

    def list_platform_search_jobs(self, db: Session) -> AdminSearchJobListResponse:
        rows = db.execute(
            select(SearchJob, Workspace)
            .join(Workspace, Workspace.id == SearchJob.workspace_id)
            .order_by(SearchJob.queued_at.desc(), SearchJob.id.desc())
            .limit(100)
        ).all()
        return AdminSearchJobListResponse(
            items=[self._search_job_response(job, workspace) for job, workspace in rows]
        )

    def get_platform_ai_usage(self, db: Session) -> AdminAIUsageResponse:
        feedback_counts = db.execute(
            select(AIFeedback.rating, func.count(AIFeedback.id))
            .group_by(AIFeedback.rating)
            .order_by(AIFeedback.rating.asc())
        ).all()
        latest_feedback = db.execute(
            select(AIFeedback, Workspace)
            .join(Workspace, Workspace.id == AIFeedback.workspace_id)
            .order_by(AIFeedback.created_at.desc(), AIFeedback.id.desc())
            .limit(20)
        ).all()
        recent_analyses = db.execute(
            select(AIAnalysisSnapshot, Lead, Workspace)
            .join(Lead, Lead.id == AIAnalysisSnapshot.lead_id)
            .join(Workspace, Workspace.id == Lead.workspace_id)
            .order_by(AIAnalysisSnapshot.created_at.desc(), AIAnalysisSnapshot.id.desc())
            .limit(100)
        ).all()
        flagged_analyses: list[AdminFlaggedAnalysisResponse] = []
        for snapshot, lead, workspace in recent_analyses:
            raw_confidence = snapshot.output_json.get("confidence")
            confidence = (
                float(raw_confidence) if isinstance(raw_confidence, int | float) else 0.0
            )
            raw_risks = snapshot.output_json.get("risks_or_uncertainties")
            risks = (
                [str(risk) for risk in raw_risks if isinstance(risk, str)]
                if isinstance(raw_risks, list)
                else []
            )
            if confidence > 0.6 and not risks:
                continue
            flagged_analyses.append(
                AdminFlaggedAnalysisResponse(
                    public_id=snapshot.public_id,
                    workspace_public_id=workspace.public_id,
                    workspace_name=workspace.name,
                    lead_public_id=lead.public_id,
                    lead_name=lead.company_name,
                    confidence=confidence,
                    risks_or_uncertainties=risks,
                    created_at=snapshot.created_at,
                )
            )
            if len(flagged_analyses) == 20:
                break
        return AdminAIUsageResponse(
            analyses_count=self._count(db, select(func.count(AIAnalysisSnapshot.id))),
            evidence_rows_count=self._count(db, select(func.count(AIAnalysisEvidence.id))),
            feedback_counts=[
                AdminAIFeedbackSummaryResponse(rating=str(rating), count=int(count or 0))
                for rating, count in feedback_counts
            ],
            latest_feedback=[
                AdminAIFeedbackResponse(
                    public_id=feedback.public_id,
                    workspace_public_id=workspace.public_id,
                    rating=feedback.rating,
                    correction_text=feedback.correction_text,
                    created_at=feedback.created_at,
                )
                for feedback, workspace in latest_feedback
            ],
            flagged_analyses=flagged_analyses,
        )

    def get_platform_feature_health(self, db: Session) -> AdminFeatureHealthResponse:
        signal_rows = db.execute(
            select(LeadSignal.signal_type, func.count(LeadSignal.id))
            .group_by(LeadSignal.signal_type)
            .order_by(func.count(LeadSignal.id).desc(), LeadSignal.signal_type.asc())
            .limit(10)
        ).all()
        band_rows = db.execute(
            select(LeadScore.band, func.count(LeadScore.id))
            .group_by(LeadScore.band)
            .order_by(func.count(LeadScore.id).desc(), LeadScore.band.asc())
        ).all()
        failed_rows = db.execute(
            select(SearchJob, Workspace)
            .join(Workspace, Workspace.id == SearchJob.workspace_id)
            .where(SearchJob.status.in_(["failed", "partially_completed"]))
            .order_by(SearchJob.finished_at.desc(), SearchJob.id.desc())
            .limit(10)
        ).all()
        return AdminFeatureHealthResponse(
            icp_profiles_count=self._count(db, select(func.count(IcpProfile.id))),
            lead_signals_count=self._count(db, select(func.count(LeadSignal.id))),
            scoring_versions_count=self._count(db, select(func.count(ScoringConfigVersion.id))),
            lead_scores_count=self._count(db, select(func.count(LeadScore.id))),
            ai_evidence_count=self._count(db, select(func.count(AIAnalysisEvidence.id))),
            ai_feedback_count=self._count(db, select(func.count(AIFeedback.id))),
            top_signal_types=[
                AdminUsageMetricResponse(
                    metric_key=str(signal_type), current_value=int(count or 0)
                )
                for signal_type, count in signal_rows
            ],
            priority_band_distribution=[
                AdminUsageMetricResponse(metric_key=str(band), current_value=int(count or 0))
                for band, count in band_rows
            ],
            failed_jobs=[
                self._search_job_response(job, workspace) for job, workspace in failed_rows
            ],
        )

    def _to_catalog_response(self, item: WorkspaceServiceCatalogItem) -> ServiceCatalogItemResponse:
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

    def _get_workspace_or_404(self, db: Session, public_id: str) -> Workspace:
        workspace = db.scalar(select(Workspace).where(Workspace.public_id == public_id))
        if workspace is None:
            raise NotFoundError("Workspace was not found.")
        return workspace

    def _workspace_summary(
        self, db: Session, workspace: Workspace
    ) -> AdminWorkspaceSummaryResponse:
        owner = db.get(User, workspace.owner_user_id) if workspace.owner_user_id else None
        subscription = self._workspace_subscription(db, workspace)
        return AdminWorkspaceSummaryResponse(
            public_id=workspace.public_id,
            name=workspace.name,
            slug=workspace.slug,
            status=workspace.status,
            owner_public_id=owner.public_id if owner else None,
            owner_email=owner.email if owner else None,
            users_count=self._count(
                db, select(func.count(User.id)).where(User.workspace_id == workspace.id)
            ),
            leads_count=self._count(
                db, select(func.count(Lead.id)).where(Lead.workspace_id == workspace.id)
            ),
            plan_code=subscription.plan_code if subscription else None,
            subscription_status=subscription.status if subscription else None,
            created_at=workspace.created_at,
        )

    def _user_summary(self, db: Session, user: User) -> AdminUserSummaryResponse:
        workspace = db.get(Workspace, user.workspace_id)
        if workspace is None:
            raise NotFoundError("Workspace was not found.")
        return AdminUserSummaryResponse(
            public_id=user.public_id,
            full_name=user.full_name,
            email=user.email,
            role=user.role,
            status=user.status,
            workspace_public_id=workspace.public_id,
            workspace_name=workspace.name,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
        )

    def _workspace_subscription(
        self, db: Session, workspace: Workspace
    ) -> AdminSubscriptionResponse | None:
        row = db.execute(
            select(Subscription, Plan)
            .join(Plan, Plan.id == Subscription.plan_id)
            .where(Subscription.workspace_id == workspace.id)
            .order_by(Subscription.created_at.desc(), Subscription.id.desc())
            .limit(1)
        ).first()
        if row is None:
            return None
        subscription, plan = row
        return self._subscription_response(subscription, plan, workspace)

    def _subscription_response(
        self, subscription: Subscription, plan: Plan, workspace: Workspace
    ) -> AdminSubscriptionResponse:
        return AdminSubscriptionResponse(
            public_id=subscription.public_id,
            workspace_public_id=workspace.public_id,
            workspace_name=workspace.name,
            plan_code=plan.code,
            plan_name=plan.name,
            status=subscription.status,
            billing_cycle=subscription.billing_cycle,
            started_at=subscription.started_at,
            renews_at=subscription.renews_at,
            ends_at=subscription.ends_at,
        )

    def _workspace_invoices(
        self, db: Session, workspace: Workspace, *, limit: int
    ) -> list[AdminInvoiceResponse]:
        return self._invoice_rows(db, workspace_id=workspace.id, limit=limit)

    def _invoice_rows(
        self, db: Session, *, limit: int, workspace_id: int | None = None
    ) -> list[AdminInvoiceResponse]:
        statement = (
            select(Invoice, Workspace)
            .join(Workspace, Workspace.id == Invoice.workspace_id)
            .order_by(Invoice.issued_at.desc(), Invoice.id.desc())
            .limit(limit)
        )
        if workspace_id is not None:
            statement = statement.where(Invoice.workspace_id == workspace_id)
        rows = db.execute(statement).all()
        return [
            AdminInvoiceResponse(
                public_id=invoice.public_id,
                workspace_public_id=workspace.public_id,
                workspace_name=workspace.name,
                amount=float(invoice.amount),
                currency=invoice.currency,
                status=invoice.status,
                issued_at=invoice.issued_at,
                due_at=invoice.due_at,
                paid_at=invoice.paid_at,
                items=self._invoice_items(db, invoice.id),
                payment_attempts=self._payment_attempts(db, invoice.id),
            )
            for invoice, workspace in rows
        ]

    def _workspace_usage(
        self, db: Session, workspace: Workspace
    ) -> list[AdminUsageCounterResponse]:
        counters = list(
            db.scalars(
                select(UsageCounter)
                .where(UsageCounter.workspace_id == workspace.id)
                .order_by(UsageCounter.period_end.desc(), UsageCounter.metric_key.asc())
            )
        )
        return [
            AdminUsageCounterResponse(
                workspace_public_id=workspace.public_id,
                workspace_name=workspace.name,
                metric_key=counter.metric_key,
                current_value=counter.current_value,
                period_start=counter.period_start,
                period_end=counter.period_end,
            )
            for counter in counters
        ]

    def _workspace_jobs(
        self, db: Session, workspace: Workspace, *, limit: int
    ) -> list[AdminSearchJobResponse]:
        jobs = list(
            db.scalars(
                select(SearchJob)
                .where(SearchJob.workspace_id == workspace.id)
                .order_by(SearchJob.queued_at.desc(), SearchJob.id.desc())
                .limit(limit)
            )
        )
        return [self._search_job_response(job, workspace) for job in jobs]

    def _workspace_users(self, db: Session, workspace_id: int) -> list[AdminUserSummaryResponse]:
        users = list(
            db.scalars(
                select(User)
                .where(User.workspace_id == workspace_id)
                .order_by(User.created_at.desc(), User.id.desc())
            )
        )
        return [self._user_summary(db, user) for user in users]

    def _workspace_provider_errors(
        self, db: Session, workspace: Workspace, *, limit: int
    ) -> list[AdminProviderFetchResponse]:
        fetches = list(
            db.scalars(
                select(ProviderFetch)
                .where(
                    ProviderFetch.workspace_id == workspace.id,
                    or_(
                        ProviderFetch.status != ProviderFetchStatus.OK.value,
                        ProviderFetch.error_message.is_not(None),
                    ),
                )
                .order_by(ProviderFetch.started_at.desc(), ProviderFetch.id.desc())
                .limit(limit)
            )
        )
        return [self._provider_fetch_response(fetch, workspace) for fetch in fetches]

    def _workspace_audit_logs(
        self, db: Session, workspace_id: int, *, limit: int
    ) -> list[AdminAuditLogResponse]:
        rows = db.execute(
            select(AuditLog, User.public_id)
            .outerjoin(User, User.id == AuditLog.actor_user_id)
            .where(AuditLog.workspace_id == workspace_id)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(limit)
        ).all()
        return [
            AdminAuditLogResponse(
                public_id=log.public_id,
                actor_user_public_id=actor_public_id,
                event_name=log.event_name,
                details=log.details,
                created_at=log.created_at,
            )
            for log, actor_public_id in rows
        ]

    def _search_job_response(
        self, job: SearchJob, workspace: Workspace
    ) -> AdminSearchJobResponse:
        return AdminSearchJobResponse(
            public_id=job.public_id,
            workspace_public_id=workspace.public_id,
            workspace_name=workspace.name,
            business_type=job.business_type,
            city=job.city,
            status=SearchJobStatus(job.status),
            queued_at=job.queued_at,
            finished_at=job.finished_at,
            candidates_found=job.candidates_found,
            leads_upserted=job.leads_upserted,
            provider_error_count=job.provider_error_count,
        )

    def _provider_fetch_response(
        self, fetch: ProviderFetch, workspace: Workspace
    ) -> AdminProviderFetchResponse:
        return AdminProviderFetchResponse(
            public_id=fetch.public_id,
            workspace_public_id=workspace.public_id,
            workspace_name=workspace.name,
            provider=fetch.provider,
            engine=fetch.engine,
            mode=fetch.mode,
            status=fetch.status,
            http_status=fetch.http_status,
            error_message=fetch.error_message,
            started_at=fetch.started_at,
            finished_at=fetch.finished_at,
        )

    def _workspace_ai_analysis_count(self, db: Session, workspace_id: int) -> int:
        return self._count(
            db,
            select(func.count(AIAnalysisSnapshot.id))
            .join(Lead, Lead.id == AIAnalysisSnapshot.lead_id)
            .where(Lead.workspace_id == workspace_id),
        )

    def _workspace_lead_score_count(self, db: Session, workspace_id: int) -> int:
        return self._count(
            db,
            select(func.count(LeadScore.id))
            .join(Lead, Lead.id == LeadScore.lead_id)
            .where(Lead.workspace_id == workspace_id),
        )

    def _invoice_items(self, db: Session, invoice_id: int) -> list[AdminInvoiceItemResponse]:
        items = list(
            db.scalars(
                select(InvoiceItem)
                .where(InvoiceItem.invoice_id == invoice_id)
                .order_by(InvoiceItem.id.asc())
            )
        )
        return [
            AdminInvoiceItemResponse(
                description=item.description,
                amount=float(item.amount),
                quantity=item.quantity,
            )
            for item in items
        ]

    def _payment_attempts(
        self, db: Session, invoice_id: int
    ) -> list[AdminPaymentAttemptResponse]:
        attempts = list(
            db.scalars(
                select(PaymentAttempt)
                .where(PaymentAttempt.invoice_id == invoice_id)
                .order_by(PaymentAttempt.attempted_at.desc(), PaymentAttempt.id.desc())
            )
        )
        return [
            AdminPaymentAttemptResponse(
                public_id=attempt.public_id,
                status=attempt.status,
                simulated_result=attempt.simulated_result,
                attempted_at=attempt.attempted_at,
                error_message=attempt.error_message,
            )
            for attempt in attempts
        ]

    def _monthly_recurring_revenue(self, db: Session) -> float:
        rows = db.execute(
            select(Subscription.billing_cycle, Plan.monthly_price, Plan.yearly_price)
            .join(Plan, Plan.id == Subscription.plan_id)
            .where(Subscription.status.in_(["trialing", "active", "past_due"]))
        ).all()
        total = Decimal("0.00")
        for billing_cycle, monthly_price, yearly_price in rows:
            if billing_cycle == "yearly":
                total += Decimal(yearly_price or 0) / Decimal("12")
            else:
                total += Decimal(monthly_price or 0)
        return float(total)

    def _count(self, db: Session, statement: Any) -> int:
        return int(db.scalar(statement) or 0)
