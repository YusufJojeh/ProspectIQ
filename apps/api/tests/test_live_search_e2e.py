from __future__ import annotations

import json
import os

import pytest
from sqlalchemy import select
from test_workspace_e2e import _build_session_factory, _seed_workspace

from app.core.config import clear_settings_cache, get_settings
from app.modules.provider_serpapi.models import ProviderSettings
from app.modules.provider_serpapi.service import SerpApiService
from app.modules.search_jobs.models import SearchJob
from app.modules.users.models import User, Workspace
from app.shared.enums.jobs import ProviderFetchStatus, WebsitePreference


def _require_live_search_enabled() -> None:
    clear_settings_cache()
    settings = get_settings()
    if os.getenv("PROSPECTIQ_LIVE_SEARCH_E2E") != "1":
        pytest.skip("Set PROSPECTIQ_LIVE_SEARCH_E2E=1 to spend two live SerpAPI searches.")
    if not settings.has_serpapi_configured:
        pytest.skip("SERPAPI_API_KEY is required for live search E2E.")


@pytest.mark.parametrize(
    ("case_name", "business_type", "city", "hl", "gl", "expected_query_fragment"),
    [
        (
            "arabic_restaurants_jeddah",
            "\u0645\u0637\u0627\u0639\u0645",
            "\u062c\u062f\u0629",
            "ar",
            "sa",
            "\u0645\u0637\u0627\u0639\u0645 \u0641\u064a \u062c\u062f\u0629",
        ),
        ("english_dentists_istanbul", "dentist", "Istanbul", "en", "tr", "dentist in Istanbul"),
    ],
)
def test_live_serpapi_maps_search_e2e_minimal_budget(
    case_name: str,
    business_type: str,
    city: str,
    hl: str,
    gl: str,
    expected_query_fragment: str,
) -> None:
    """Opt-in live smoke test.

    Budget: exactly one Google Maps search per parameterized case. It does not
    run the full discovery orchestrator, so it avoids place lookups, web-search
    validation, enrichers, and OpenAI usage.
    """
    _require_live_search_enabled()
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with session_factory() as db:
        workspace = db.scalar(
            select(Workspace).where(Workspace.public_id == seed.workspace_public_id)
        )
        user = db.scalar(select(User).where(User.email == seed.admin_email))
        assert workspace is not None
        assert user is not None

        provider_settings = db.scalar(
            select(ProviderSettings).where(ProviderSettings.workspace_id == workspace.id)
        )
        assert provider_settings is not None
        provider_settings.hl = hl
        provider_settings.gl = gl
        provider_settings.google_domain = "google.com"

        job = SearchJob(
            workspace_id=workspace.id,
            requested_by_user_id=user.id,
            business_type=business_type,
            city=city,
            max_results=3,
            website_preference=WebsitePreference.ANY.value,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        fetch, payload = SerpApiService().maps_search(
            db,
            workspace_id=workspace.id,
            search_job_id=job.id,
            business_type=business_type,
            city=city,
            region=None,
            radius_km=None,
            keyword_filter=None,
        )

    assert fetch.status == ProviderFetchStatus.OK.value, fetch.error_message
    assert fetch.request_params_json["q"] == expected_query_fragment
    assert fetch.request_params_json["hl"] == hl
    assert fetch.request_params_json["gl"] == gl
    assert isinstance(payload.get("local_results"), list), case_name
    assert payload["local_results"], case_name
    top_titles = [
        str(item.get("title"))
        for item in payload["local_results"][:5]
        if isinstance(item, dict) and item.get("title")
    ]
    print(
        json.dumps(
            {
                "case": case_name,
                "query": fetch.request_params_json["q"],
                "results": len(payload["local_results"]),
                "top_titles": top_titles,
            },
            ensure_ascii=True,
        )
    )
