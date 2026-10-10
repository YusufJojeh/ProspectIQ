from __future__ import annotations

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.modules.leads.models import Lead
from app.modules.provider_serpapi.models import ProviderNormalizedFact
from app.modules.provider_serpapi.repository import (
    ProviderEvidenceRepository,
    _compute_source_unique_id,
)
from app.modules.search_jobs.models import SearchJob
from app.modules.search_jobs.schemas import SearchJobCreateRequest
from app.modules.search_jobs.service import SearchJobService
from app.modules.users.models import Role, User, Workspace


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


def _seed_lead(db: Session) -> Lead:
    workspace = Workspace(name="Dedup Workspace")
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    lead = Lead(
        workspace_id=workspace.id,
        company_name="North Dental",
        city="Istanbul",
        data_completeness=0.6,
        data_confidence=0.8,
        has_website=False,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def _fact(lead: Lead, *, source_unique_id: str, confidence: float) -> ProviderNormalizedFact:
    return ProviderNormalizedFact(
        workspace_id=lead.workspace_id,
        lead_id=lead.id,
        provider_fetch_id=0,
        source_type="maps_search",
        source_unique_id=source_unique_id,
        company_name=lead.company_name,
        confidence=confidence,
        completeness=0.6,
        facts_json={},
    )


def _fact_count(db: Session, lead_id: int) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(ProviderNormalizedFact)
            .where(ProviderNormalizedFact.lead_id == lead_id)
        )
        or 0
    )


def test_source_unique_id_prefers_stable_provider_identities() -> None:
    common = {"company_name": "A", "address": None, "phone": None, "website_domain": None}
    assert (
        _compute_source_unique_id(place_id="p1", data_id="d1", data_cid="c1", **common)
        == "place_p1"
    )
    assert _compute_source_unique_id(place_id=None, data_id="d1", data_cid="c1", **common) == (
        "did_d1"
    )
    hashed = _compute_source_unique_id(place_id=None, data_id=None, data_cid=None, **common)
    assert hashed.startswith("hash_")
    assert hashed == _compute_source_unique_id(place_id=None, data_id=None, data_cid=None, **common)


def test_upsert_updates_existing_fact_for_same_source_identity() -> None:
    repository = ProviderEvidenceRepository()
    with _build_session_factory()() as db:
        lead = _seed_lead(db)
        first = repository.upsert_normalized_fact(
            db, _fact(lead, source_unique_id="place_p1", confidence=0.5)
        )
        second = repository.upsert_normalized_fact(
            db, _fact(lead, source_unique_id="place_p1", confidence=0.9)
        )

        assert second.id == first.id
        assert second.confidence == 0.9
        assert _fact_count(db, lead.id) == 1


def test_upsert_without_source_identity_never_merges_facts() -> None:
    repository = ProviderEvidenceRepository()
    with _build_session_factory()() as db:
        lead = _seed_lead(db)
        repository.upsert_normalized_fact(db, _fact(lead, source_unique_id="", confidence=0.5))
        repository.upsert_normalized_fact(db, _fact(lead, source_unique_id="", confidence=0.9))

        assert _fact_count(db, lead.id) == 2


def _create_job(db: Session, workspace_id: int, user_id: int, **overrides: object) -> SearchJob:
    payload = {"business_type": "Dentist", "city": "Istanbul", "max_results": 10, **overrides}
    return SearchJobService().create_search_job(
        db,
        SearchJobCreateRequest.model_validate(payload),
        workspace_id=workspace_id,
        requested_by_user_id=user_id,
    )


def test_identical_active_search_returns_existing_job_but_new_filters_do_not() -> None:
    with _build_session_factory()() as db:
        db.add(Role(key="admin", label="Administrator"))
        workspace = Workspace(name="Dedup Workspace")
        db.add(workspace)
        db.commit()
        db.refresh(workspace)
        user = User(
            workspace_id=workspace.id,
            email="admin@example.com",
            full_name="Admin User",
            hashed_password="hashed",
            role="admin",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        first = _create_job(db, workspace.id, user.id)
        duplicate = _create_job(db, workspace.id, user.id, business_type="  dentist ")
        filtered = _create_job(db, workspace.id, user.id, min_rating=4.0)

        assert duplicate.id == first.id
        assert filtered.id != first.id
        assert first.dedup_fingerprint and filtered.dedup_fingerprint
