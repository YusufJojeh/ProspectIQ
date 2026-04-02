from __future__ import annotations

import argparse
from datetime import UTC, datetime

from alembic import command
from alembic.config import Config

from app.core.database import SessionLocal
from app.modules.ai_analysis.models import PromptTemplate
from app.modules.provider_serpapi.models import ProviderSettings
from app.modules.scoring.models import ScoringConfigVersion, WorkspaceScoringActive
from app.modules.users.service import seed_default_workspace_and_admin


def run_migrations() -> None:
    config = Config("alembic.ini")
    command.upgrade(config, "head")


def seed() -> None:
    with SessionLocal() as db:
        workspace, admin = seed_default_workspace_and_admin(db)

        existing_provider_settings = db.query(ProviderSettings).filter(ProviderSettings.workspace_id == workspace.id).one_or_none()
        if existing_provider_settings is None:
            db.add(
                ProviderSettings(
                    workspace_id=workspace.id,
                    hl="en",
                    gl="tr",
                    google_domain="google.com",
                    enrich_top_n=20,
                )
            )
            db.commit()

        active = db.query(WorkspaceScoringActive).filter(WorkspaceScoringActive.workspace_id == workspace.id).one_or_none()
        if active is None:
            version = ScoringConfigVersion(
                workspace_id=workspace.id,
                created_by_user_id=admin.id,
                weights_json={
                    "local_trust": 0.25,
                    "website_presence": 0.25,
                    "search_visibility": 0.2,
                    "opportunity": 0.2,
                    "data_confidence": 0.1,
                },
                thresholds_json={
                    "high_min": 75,
                    "medium_min": 55,
                    "low_min": 35,
                    "confidence_min": 0.45,
                },
                note="Seed default scoring config",
            )
            db.add(version)
            db.commit()
            db.refresh(version)
            db.add(
                WorkspaceScoringActive(
                    workspace_id=workspace.id,
                    active_scoring_config_version_id=version.id,
                    updated_at=datetime.now(tz=UTC),
                )
            )
            db.commit()

        prompt = db.query(PromptTemplate).filter(PromptTemplate.workspace_id == workspace.id, PromptTemplate.is_active == True).first()  # noqa: E712
        if prompt is None:
            db.add(
                PromptTemplate(
                    workspace_id=workspace.id,
                    name="Default lead analysis",
                    template_text="Analyze the lead using only normalized facts and deterministic score context.",
                    is_active=True,
                    created_by_user_id=admin.id,
                )
            )
            db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed LeadScope AI (ProspectIQ) database.")
    parser.add_argument("--migrate", action="store_true", help="Run alembic migrations before seeding.")
    args = parser.parse_args()

    if args.migrate:
        run_migrations()
    seed()
    print("Seed completed.")


if __name__ == "__main__":
    main()
