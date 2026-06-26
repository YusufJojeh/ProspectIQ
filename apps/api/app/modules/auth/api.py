from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rate_limit import check_rate_limit
from app.modules.auth.policies import get_current_user
from app.modules.auth.schemas import (
    AuthenticatedUser,
    LoginRequest,
    LogoutResponse,
    SignupRequest,
    TokenResponse,
)
from app.modules.auth.service import AuthService
from app.modules.users.models import User

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    check_rate_limit(request, scope="auth:login", limit=10, window_seconds=60)
    return AuthService().authenticate(db, payload)


@router.post("/signup", response_model=TokenResponse)
def signup(
    request: Request, payload: SignupRequest, db: Session = Depends(get_db)
) -> TokenResponse:
    check_rate_limit(request, scope="auth:signup", limit=5, window_seconds=60)
    return AuthService().signup(db, payload)


@router.post("/logout", response_model=LogoutResponse)
def logout() -> LogoutResponse:
    return AuthService().logout()


@router.get("/me", response_model=AuthenticatedUser)
def me(current_user: User = Depends(get_current_user)) -> AuthenticatedUser:
    return AuthService().me(current_user)
