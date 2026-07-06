from __future__ import annotations

import importlib

from sqlalchemy import select

from app.modules.scoring.models import ScoringConfigVersion, WorkspaceScoringActive
from app.modules.scoring.schemas import ScoringWeights
from app.modules.scoring.service import ScoringConfigService
from app.modules.search_jobs.models import SearchJob
from tests.test_lead_discovery_orchestrator import _build_session_factory, _seed_job

repair_migration = importlib.import_module("migrations.versions.0019_repair_scoring_weight_totals")


def test_default_scoring_weights_sum_to_one() -> None:
    weights = ScoringWeights()

    assert sum(weights.model_dump().values()) == 1.0


def test_active_scoring_versions_validate_and_sum_to_one() -> None:
    session_factory = _build_session_factory()
    job_public_id = _seed_job(session_factory)
    with session_factory() as db:
        job = db.scalar(select(SearchJob).where(SearchJob.public_id == job_public_id))
        assert job is not None

        ScoringConfigService().ensure_active_version(
            db,
            job.workspace_id,
            created_by_user_id=job.requested_by_user_id,
        )
        active_versions = list(
            db.scalars(
                select(ScoringConfigVersion)
                .join(
                    WorkspaceScoringActive,
                    WorkspaceScoringActive.active_scoring_config_version_id
                    == ScoringConfigVersion.id,
                )
                .where(WorkspaceScoringActive.workspace_id == job.workspace_id)
            )
        )

    assert active_versions
    for version in active_versions:
        weights = ScoringWeights.model_validate(version.weights_json)
        assert sum(weights.model_dump().values()) == 1.0


def test_repair_migration_replaces_invalid_active_weight_total_with_canonical_weights() -> None:
    invalid_weights = {
        "local_trust": 0.18,
        "website_presence": 0.18,
        "search_visibility": 0.14,
        "opportunity": 0.14,
        "data_confidence": 0.08,
        "review_score": 0.13,
        "news_presence": 0.05,
        "web_search_confidence": 0.20,
    }

    assert repair_migration._weight_total(invalid_weights) == repair_migration.Decimal("1.10")

    repaired = repair_migration._repair_weights(invalid_weights)

    assert repaired == repair_migration.CANONICAL_WEIGHTS
    assert repair_migration._weight_total(repaired) == repair_migration.Decimal("1.00")
    ScoringWeights.model_validate(repaired)


def test_repair_migration_preserves_valid_custom_weights() -> None:
    valid_custom_weights = {
        "local_trust": 0.2,
        "website_presence": 0.2,
        "search_visibility": 0.1,
        "opportunity": 0.2,
        "data_confidence": 0.1,
        "review_score": 0.1,
        "news_presence": 0.0,
        "web_search_confidence": 0.1,
    }

    assert repair_migration._repair_weights(valid_custom_weights) == valid_custom_weights
    ScoringWeights.model_validate(valid_custom_weights)
