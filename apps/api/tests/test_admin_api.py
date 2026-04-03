from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.modules.ai_analysis.models import PromptTemplate
from app.modules.provider_serpapi.models import ProviderFetch
from app.modules.search_jobs.models import SearchJob
from app.modules.users.models import Role, User, Workspace
from app.shared.enums.jobs import ProviderFetchStatus, SearchJobStatus


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


def _seed_admin_workspace(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as db:
        db.add_all(
            [
                Role(key="admin", label="Administrator"),
                Role(key="agency_manager", label="Agency Manager"),
                Role(key="sales_user", label="Sales User"),
            ]
        )
        db.commit()

        workspace = Workspace(public_id="ws_test", name="Test Workspace")
        db.add(workspace)
        db.commit()
        db.refresh(workspace)

        admin = User(
            workspace_id=workspace.id,
            email="admin@example.com",
            full_name="Admin User",
            hashed_password=hash_password("AdminPass123"),
            role="admin",
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)

        db.add(
            PromptTemplate(
                workspace_id=workspace.id,
                name="Active prompt",
                template_text="Use evidence only.",
                is_active=True,
                created_by_user_id=admin.id,
            )
        )
        db.add(
            SearchJob(
                workspace_id=workspace.id,
                requested_by_user_id=admin.id,
                business_type="Dentist",
                city="Istanbul",
                max_results=25,
                status=SearchJobStatus.FAILED.value,
                provider_error_count=2,
            )
        )
        db.commit()
        failed_job = db.query(SearchJob).order_by(SearchJob.id.desc()).first()
        assert failed_job is not None
        db.add(
            ProviderFetch(
                workspace_id=workspace.id,
                provider="serpapi",
                engine="google_maps",
                mode="maps_search",
                search_job_id=failed_job.id,
                request_fingerprint="fingerprint-1",
                request_params_json={"q": "dentist istanbul"},
                status=ProviderFetchStatus.ERROR.value,
                http_status=500,
                error_message="Provider timeout",
            )
        )
        db.commit()


def _login(client: TestClient) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"workspace": "ws_test", "email": "admin@example.com", "password": "AdminPass123"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@contextmanager
def _override_client(
    session_factory: sessionmaker[Session],
) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        with session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def test_admin_can_manage_prompt_templates_and_view_operations_health() -> None:
    session_factory = _build_session_factory()
    _seed_admin_workspace(session_factory)

    with _override_client(session_factory) as client:
        token = _login(client)
        headers = {"Authorization": f"Bearer {token}"}

        list_response = client.get("/api/v1/admin/prompt-templates", headers=headers)
        create_response = client.post(
            "/api/v1/admin/prompt-templates",
            headers=headers,
            json={
                "name": "Sharper prompt",
                "template_text": "Use stored facts only and cite the score reasons.",
                "activate": True,
            },
        )
        health_response = client.get("/api/v1/admin/operations/health", headers=headers)

    assert list_response.status_code == 200
    assert len(list_response.json()["items"]) == 1

    assert create_response.status_code == 200
    assert create_response.json()["name"] == "Sharper prompt"
    assert create_response.json()["is_active"] is True

    assert health_response.status_code == 200
    payload = health_response.json()
    assert payload["database_ok"] is True
    assert payload["failed_jobs_last_7_days"] >= 1
    assert payload["provider_failures_last_7_days"] >= 1
    assert payload["recent_failed_jobs"][0]["status"] == "failed"
    assert payload["recent_provider_failures"][0]["status"] == "error"


def test_admin_operational_health_sql_is_mariadb_safe() -> None:
    statement = (
        select(SearchJob)
        .where(
            SearchJob.workspace_id == 1,
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

    compiled_sql = str(statement.compile(dialect=mysql.dialect()))

    assert "NULLS LAST" not in compiled_sql.upper()
