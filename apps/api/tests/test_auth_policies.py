from datetime import UTC, datetime

from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import hash_password
from app.modules.auth.policies import get_current_user, get_token_claims, require_role
from app.modules.auth.schemas import AuthTokenClaims, LoginRequest
from app.modules.auth.service import AuthService
from app.modules.users.models import User, Workspace


def build_session_factory() -> sessionmaker[Session]:
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


def seed_workspace_user(db: Session) -> tuple[Workspace, User]:
    workspace = Workspace(public_id="ws_test", name="Test Workspace")
    db.add(workspace)
    db.commit()
    db.refresh(workspace)

    user = User(
        workspace_id=workspace.id,
        email="owner@example.com",
        full_name="Owner User",
        hashed_password=hash_password("SecretPass123"),
        role="admin",
        created_at=datetime.now(tz=UTC),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return workspace, user


def test_authenticate_returns_token_for_valid_credentials() -> None:
    session_factory = build_session_factory()

    with session_factory() as db:
        workspace, _ = seed_workspace_user(db)
        response = AuthService().authenticate(
            db,
            payload=LoginRequest(
                workspace=workspace.public_id,
                email="owner@example.com",
                password="SecretPass123",
            ),
        )

    assert response.access_token
    assert response.user.workspace_public_id == workspace.public_id


def test_get_token_claims_rejects_missing_credentials() -> None:
    try:
        get_token_claims(None)
    except UnauthorizedError as exc:
        assert exc.code == "unauthorized"
    else:
        raise AssertionError("Expected UnauthorizedError for missing credentials.")


def test_get_current_user_returns_db_user(monkeypatch) -> None:
    session_factory = build_session_factory()
    with session_factory() as db:
        workspace, user = seed_workspace_user(db)
        claims = {
            "sub": user.public_id,
            "workspace_id": workspace.id,
            "workspace_public_id": workspace.public_id,
            "role": user.role,
        }
        monkeypatch.setattr(
            "app.modules.auth.policies.decode_access_token",
            lambda _: claims,
        )
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="valid-token",
        )

        resolved = get_current_user(
            claims=AuthTokenClaims.model_validate(get_token_claims(credentials)),
            db=db,
        )

    assert resolved.public_id == user.public_id


def test_require_role_raises_forbidden_for_disallowed_role() -> None:
    user = User(
        workspace_id=1,
        email="sales@example.com",
        full_name="Sales User",
        hashed_password="hashed",
        role="sales_user",
    )

    try:
        require_role("admin")(user)
    except ForbiddenError as exc:
        assert exc.code == "forbidden"
    else:
        raise AssertionError("Expected ForbiddenError for insufficient role.")
