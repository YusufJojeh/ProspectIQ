from __future__ import annotations

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.modules.search_jobs.models import SearchJob, SearchRequest
from app.modules.search_jobs.schemas import SearchJobCreateRequest
from app.modules.search_jobs.service import SearchJobService
from app.modules.users.models import Role, User, Workspace
from app.shared.enums.jobs import WebsitePreference


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


def test_create_search_job_persists_canonical_search_request() -> None:
    session_factory = _build_session_factory()
    with session_factory() as db:
        db.add(Role(key="admin", label="Administrator"))
        db.commit()

        workspace = Workspace(name="LeadScope Workspace")
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

        job = SearchJobService().create_search_job(
            db,
            SearchJobCreateRequest(
                business_type="Dentist",
                city="Istanbul",
                region="Kadikoy",
                radius_km=12,
                max_results=25,
                min_rating=4.0,
                max_rating=4.8,
                min_reviews=5,
                max_reviews=50,
                website_preference=WebsitePreference.MUST_HAVE,
                keyword_filter="implant",
            ),
            workspace_id=workspace.id,
            requested_by_user_id=user.id,
        )

        persisted_job = db.get(SearchJob, job.id)
        persisted_request = db.get(SearchRequest, job.search_request_id)

        assert persisted_job is not None
        assert persisted_request is not None
        assert persisted_request.workspace_id == workspace.id
        assert persisted_request.requested_by_user_id == user.id
        assert persisted_request.business_type == persisted_job.business_type
        assert persisted_request.city == persisted_job.city
        assert persisted_request.region == persisted_job.region
        assert persisted_request.radius_km == persisted_job.radius_km
        assert persisted_request.max_rating == persisted_job.max_rating
        assert persisted_request.max_reviews == persisted_job.max_reviews
        assert persisted_request.website_preference == persisted_job.website_preference
        assert persisted_request.keyword_filter == persisted_job.keyword_filter
        assert db.scalar(select(func.count(SearchRequest.id))) == 1
