from __future__ import annotations

from datetime import UTC, datetime

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import clear_settings_cache
from app.core.database import Base
from app.modules.leads.models import Lead
from app.modules.provider_serpapi.client import SerpApiClient
from app.modules.provider_serpapi.engines.maps_place import build_maps_place_params
from app.modules.provider_serpapi.models import LeadIdentity, ProviderNormalizedFact
from app.modules.provider_serpapi.normalizers.maps_local_normalizer import MapsLocalNormalizer
from app.modules.provider_serpapi.normalizers.web_search_normalizer import WebSearchNormalizer
from app.modules.provider_serpapi.repository import ProviderEvidenceRepository
from app.modules.provider_serpapi.schemas import LeadIdentityCandidate, PlaceLookupKey
from app.modules.users.models import Workspace


def _build_session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )


def test_maps_local_normalizer_ignores_directory_domains_as_official_websites() -> None:
    normalizer = MapsLocalNormalizer()

    candidates = normalizer.normalize(
        {
            "local_results": [
                {
                    "title": "North Dental",
                    "website": "https://www.facebook.com/north-dental",
                    "address": "Kadikoy, Istanbul, Turkey",
                    "phone": "+90 555 111 2233",
                }
            ]
        }
    )

    assert len(candidates) == 1
    assert candidates[0].website_url is None
    assert candidates[0].website_domain is None
    assert all(identity.identity_type != "website_domain" for identity in candidates[0].identities)


def test_web_search_normalizer_skips_directory_domains_and_uses_business_domain() -> None:
    result = WebSearchNormalizer().normalize(
        {
            "organic_results": [
                {"position": 1, "link": "https://www.yelp.com/biz/north-dental"},
                {"position": 2, "link": "https://northdental.example/contact"},
            ]
        }
    )

    assert result.website_url == "https://northdental.example/contact"
    assert result.website_domain == "northdental.example"
    assert result.facts["source"] == "organic_results"
    assert result.facts["position"] == 2


def test_repository_prefers_stronger_identity_match_over_first_match() -> None:
    session_factory = _build_session_factory()
    repository = ProviderEvidenceRepository()

    with session_factory() as db:
        workspace = Workspace(name="LeadScope Workspace")
        db.add(workspace)
        db.commit()
        db.refresh(workspace)

        weaker = Lead(
            workspace_id=workspace.id,
            company_name="North Dental Listing",
            city="Istanbul",
            address="Kadikoy, Istanbul, Turkey",
            data_completeness=0.3,
            data_confidence=0.3,
            has_website=False,
        )
        stronger = Lead(
            workspace_id=workspace.id,
            company_name="North Dental Clinic",
            city="Istanbul",
            address="Kadikoy, Istanbul, Turkey",
            data_completeness=0.7,
            data_confidence=0.8,
            has_website=False,
        )
        db.add_all([weaker, stronger])
        db.commit()
        db.refresh(weaker)
        db.refresh(stronger)

        db.add_all(
            [
                LeadIdentity(
                    workspace_id=workspace.id,
                    lead_id=weaker.id,
                    identity_type="fingerprint",
                    identity_value="north|istanbul|kadikoy",
                    created_at=datetime.now(tz=UTC),
                ),
                LeadIdentity(
                    workspace_id=workspace.id,
                    lead_id=stronger.id,
                    identity_type="phone",
                    identity_value="+905551112233",
                    created_at=datetime.now(tz=UTC),
                ),
            ]
        )
        db.commit()

        resolved = repository.find_lead_by_identities(
            db,
            workspace_id=workspace.id,
            identities=[
                LeadIdentityCandidate(
                    identity_type="fingerprint",
                    identity_value="north|istanbul|kadikoy",
                ),
                LeadIdentityCandidate(
                    identity_type="phone",
                    identity_value="+905551112233",
                ),
            ],
        )

    assert resolved is not None
    assert resolved.public_id == stronger.public_id


def test_serpapi_client_retries_payload_rate_limit_then_succeeds(monkeypatch) -> None:
    monkeypatch.setenv("SERPAPI_API_KEY", "12345678901234567890123456789012")
    clear_settings_cache()
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(200, json={"error": "Rate limit exceeded"})
        return httpx.Response(
            200,
            json={
                "search_metadata": {"id": "search-2"},
                "local_results": [{"title": "North Dental"}],
            },
        )

    client = SerpApiClient()
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        result = client.search({"engine": "google_maps", "q": "dentist in istanbul"})
    finally:
        client._client.close()
        clear_settings_cache()

    assert calls["count"] == 2
    assert result.ok is True
    assert result.serpapi_search_id == "search-2"


def test_maps_place_params_uses_place_id_when_lookup_requires_it() -> None:
    params = build_maps_place_params(
        lookup=PlaceLookupKey(key_type="place_id", value="ChIJ123"),
        hl="en",
        gl="tr",
        google_domain="google.com",
    )

    assert params["place_id"] == "ChIJ123"
    assert "data" not in params
    assert "data_cid" not in params


def test_repository_prefers_place_id_for_place_lookup() -> None:
    session_factory = _build_session_factory()
    repository = ProviderEvidenceRepository()

    with session_factory() as db:
        workspace = Workspace(name="LeadScope Workspace")
        db.add(workspace)
        db.commit()
        db.refresh(workspace)

        lead = Lead(
            workspace_id=workspace.id,
            company_name="North Dental",
            city="Istanbul",
            address="Kadikoy, Istanbul, Turkey",
            data_completeness=0.6,
            data_confidence=0.8,
            has_website=False,
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)

        lead_id = lead.id
        repository.add_normalized_fact(
            db,
            fact=ProviderNormalizedFact(
                workspace_id=workspace.id,
                lead_id=lead_id,
                provider_fetch_id=0,
                source_type="maps_search",
                data_cid="123456",
                data_id="0xabc:0xdef",
                place_id="ChIJNorthDental",
                company_name=lead.company_name,
                category="Dentist",
                address=lead.address,
                city=lead.city,
                phone=None,
                website_url=None,
                website_domain=None,
                rating=4.6,
                review_count=20,
                lat=41.0,
                lng=29.0,
                confidence=0.8,
                completeness=0.6,
                facts_json={},
            ),
        )

        lookup = repository.get_best_place_lookup(db, lead_id)

    assert lookup is not None
    assert lookup.key_type == "place_id"
    assert lookup.value == "ChIJNorthDental"
