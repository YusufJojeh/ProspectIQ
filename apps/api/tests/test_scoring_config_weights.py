from __future__ import annotations

import importlib

from app.modules.scoring.schemas import ScoringWeights

repair_migration = importlib.import_module("migrations.versions.0019_repair_scoring_weight_totals")


def test_default_scoring_weights_sum_to_one() -> None:
    weights = ScoringWeights()

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
