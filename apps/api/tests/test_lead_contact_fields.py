from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.enrichers.linkedin import LinkedInEnricher
from app.modules.exports.service import ExportService
from app.modules.leads.models import Lead
from app.modules.leads.schemas import LeadResponse
from app.modules.provider_serpapi.client import ProviderCallResult
from app.modules.provider_serpapi.engines.linkedin import (
    build_linkedin_company_params,
    extract_company_url,
)
from app.modules.search_jobs.models import SearchJob  # noqa: F401  (register FK target)
from app.modules.users.models import User, Workspace
from app.shared.utils.branding import derive_logo_url, normalize_domain


def _build_session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session
    )


def _result(payload: dict[str, Any] | None, *, ok: bool = True) -> ProviderCallResult:
    now = datetime.now(tz=UTC)
    return ProviderCallResult(
        ok=ok,
        status_code=200 if ok else 500,
        payload=payload,
        error_message=None,
        serpapi_search_id=None,
        started_at=now,
        finished_at=now,
    )


class _FakeClient:
    def __init__(self, result: ProviderCallResult) -> None:
        self._result = result

    def search(self, params: dict[str, Any], *, max_attempts: int = 3) -> ProviderCallResult:
        return self._result


def test_normalize_domain_strips_scheme_and_path() -> None:
    assert normalize_domain("https://www.Acme.com/contact") == "acme.com"
    assert normalize_domain("acme.io") == "acme.io"
    assert normalize_domain("not-a-domain") is None
    assert normalize_domain(None) is None


def test_derive_logo_url_uses_domain() -> None:
    assert derive_logo_url("acme.com") == "https://logo.clearbit.com/acme.com"
    assert derive_logo_url(None, "https://acme.com/x") == "https://logo.clearbit.com/acme.com"
    assert derive_logo_url(None, None) is None


def test_linkedin_params_and_extraction() -> None:
    params = build_linkedin_company_params(company_name="North Dental", city="Istanbul")
    assert params["engine"] == "google"
    assert "linkedin.com/company" in params["q"]
    assert "North Dental" in params["q"]

    payload = {
        "organic_results": [
            {"link": "https://example.com/north"},
            {"link": "https://www.linkedin.com/company/north-dental"},
        ]
    }
    assert extract_company_url(_result(payload)) == "https://www.linkedin.com/company/north-dental"
    assert extract_company_url(_result({"organic_results": []})) is None
    assert extract_company_url(_result(None, ok=False)) is None


def test_linkedin_enricher_emits_url() -> None:
    payload = {"organic_results": [{"link": "https://linkedin.com/company/acme"}]}
    enricher = LinkedInEnricher(_FakeClient(_result(payload)))  # type: ignore[arg-type]
    lead = Lead(company_name="Acme", city="Dubai")
    result = enricher.enrich(lead, db=None)  # type: ignore[arg-type]
    assert result.ok
    assert result.data["linkedin_url"] == "https://linkedin.com/company/acme"


def test_linkedin_enricher_empty_when_no_match() -> None:
    enricher = LinkedInEnricher(_FakeClient(_result({"organic_results": []})))  # type: ignore[arg-type]
    lead = Lead(company_name="Acme", city="Dubai")
    result = enricher.enrich(lead, db=None)  # type: ignore[arg-type]
    assert not result.ok
    assert result.data == {}


def test_lead_response_exposes_contact_fields() -> None:
    fields = LeadResponse.model_fields
    for name in (
        "email",
        "email_confidence",
        "linkedin_url",
        "industry",
        "employee_count",
        "ai_opener",
        "logo_url",
    ):
        assert name in fields
        assert fields[name].is_required() is False


def _seed_lead(db: Session) -> int:
    workspace = Workspace(name="LeadScope Workspace")
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    db.add(
        User(
            workspace_id=workspace.id,
            email="admin@example.com",
            full_name="Admin User",
            hashed_password="hashed",
            role="admin",
        )
    )
    lead = Lead(
        workspace_id=workspace.id,
        company_name="North Dental",
        city="Istanbul",
        industry="Dentist",
        email="hello@north.example",
        email_confidence=0.7,
        linkedin_url="https://linkedin.com/company/north",
        employee_count=12,
        logo_url="https://logo.clearbit.com/north.example",
        review_count=24,
        rating=4.7,
        website_domain="north.example",
        has_website=True,
    )
    db.add(lead)
    db.commit()
    return workspace.id


def test_json_export_contains_contact_fields() -> None:
    session_factory = _build_session_factory()
    with session_factory() as db:
        workspace_id = _seed_lead(db)
        payload = ExportService().export_leads_json(db, workspace_id=workspace_id)
        parsed = json.loads(payload)
        assert parsed["count"] == 1
        row = parsed["items"][0]
        assert row["business_name"] == "North Dental"
        assert row["industry"] == "Dentist"
        assert row["email"] == "hello@north.example"
        assert row["linkedin_url"] == "https://linkedin.com/company/north"
        assert row["employee_count"] == 12
        assert row["logo_url"].endswith("north.example")


def test_csv_export_includes_contact_headers() -> None:
    session_factory = _build_session_factory()
    with session_factory() as db:
        workspace_id = _seed_lead(db)
        payload = ExportService().export_leads_csv(db, workspace_id=workspace_id)
        header = payload.splitlines()[0]
        for column in ("industry", "email", "linkedin_url", "employee_count", "logo_url"):
            assert column in header
        assert "hello@north.example" in payload
