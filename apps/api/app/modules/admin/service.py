from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.modules.admin.schemas import ProviderSettingsResponse, ProviderSettingsUpdateRequest
from app.modules.audit_logs.service import AuditLogService
from app.modules.provider_serpapi.models import ProviderSettings
from app.modules.scoring.models import ScoringConfigVersion
from app.modules.scoring.schemas import (
    ActiveScoringConfigResponse,
    ScoringConfigVersionCreateRequest,
    ScoringConfigVersionListResponse,
    ScoringConfigVersionResponse,
)
from app.modules.scoring.service import ScoringConfigService
from app.modules.users.models import User


class AdminService:
    def __init__(self) -> None:
        self.scoring = ScoringConfigService()
        self.audit_logs = AuditLogService()

    def get_active_scoring(self, db: Session, *, workspace_id: int) -> ActiveScoringConfigResponse:
        version = self.scoring.get_active_version(db, workspace_id)
        creator = db.get(User, version.created_by_user_id)
        return ActiveScoringConfigResponse(
            active_version=self._to_scoring_response(version, creator)
        )

    def list_scoring_versions(
        self, db: Session, *, workspace_id: int, limit: int = 50
    ) -> ScoringConfigVersionListResponse:
        items = (
            db.query(ScoringConfigVersion)
            .filter(ScoringConfigVersion.workspace_id == workspace_id)
            .order_by(ScoringConfigVersion.created_at.desc())
            .limit(limit)
            .all()
        )
        users = {
            user.id: user
            for user in db.query(User)
            .filter(User.id.in_([item.created_by_user_id for item in items]))
            .all()
        }
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
        version = (
            db.query(ScoringConfigVersion)
            .filter(
                ScoringConfigVersion.workspace_id == workspace_id,
                ScoringConfigVersion.public_id == version_public_id,
            )
            .one_or_none()
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

    def get_provider_settings(self, db: Session, *, workspace_id: int) -> ProviderSettingsResponse:
        settings = (
            db.query(ProviderSettings)
            .filter(ProviderSettings.workspace_id == workspace_id)
            .one_or_none()
        )
        if settings is None:
            settings = ProviderSettings(workspace_id=workspace_id)
            db.add(settings)
            db.commit()
            db.refresh(settings)
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
        settings = (
            db.query(ProviderSettings)
            .filter(ProviderSettings.workspace_id == workspace_id)
            .one_or_none()
        )
        if settings is None:
            settings = ProviderSettings(workspace_id=workspace_id)
            db.add(settings)
            db.commit()
            db.refresh(settings)
        if payload.hl is not None:
            settings.hl = payload.hl
        if payload.gl is not None:
            settings.gl = payload.gl
        if payload.google_domain is not None:
            settings.google_domain = payload.google_domain
        if payload.enrich_top_n is not None:
            settings.enrich_top_n = payload.enrich_top_n
        db.add(settings)
        db.commit()
        db.refresh(settings)
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
