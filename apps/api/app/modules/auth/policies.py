from collections.abc import Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import AuthTokenClaims
from app.modules.users.models import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_token_claims(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthTokenClaims:
    if credentials is None:
        raise UnauthorizedError("Missing bearer token.")
    payload = decode_access_token(credentials.credentials)
    try:
        return AuthTokenClaims.model_validate(payload)
    except Exception as exc:
        raise UnauthorizedError("Access token claims are invalid.") from exc


def get_current_user(
    claims: AuthTokenClaims = Depends(get_token_claims),
    db: Session = Depends(get_db),
) -> User:
    user = AuthRepository().get_user_by_public_id(db, claims.sub)
    if user is None:
        raise UnauthorizedError("User not found.")
    if user.workspace_id != claims.workspace_id:
        raise UnauthorizedError("Token workspace mismatch.")
    return user


def get_current_workspace_id(
    claims: AuthTokenClaims = Depends(get_token_claims),
) -> int:
    return claims.workspace_id


def require_role(*allowed: str) -> Callable[[User], User]:
    def dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise ForbiddenError("Insufficient role.")
        return user

    return dep
