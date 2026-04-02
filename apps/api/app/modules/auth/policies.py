from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import UnauthorizedError
from app.core.security import decode_access_token
from app.modules.auth.repository import AuthRepository
from app.modules.users.models import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise UnauthorizedError("Missing bearer token.")
    payload = decode_access_token(credentials.credentials)
    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise UnauthorizedError("Token subject is missing.")
    workspace_id = payload.get("workspace_id")
    if not isinstance(workspace_id, int):
        raise UnauthorizedError("Token workspace is missing.")
    user = AuthRepository().get_user_by_public_id(db, subject)
    if user is None:
        raise UnauthorizedError("User not found.")
    if user.workspace_id != workspace_id:
        raise UnauthorizedError("Token workspace mismatch.")
    return user


def get_current_workspace_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> int:
    if credentials is None:
        raise UnauthorizedError("Missing bearer token.")
    payload = decode_access_token(credentials.credentials)
    workspace_id = payload.get("workspace_id")
    if not isinstance(workspace_id, int):
        raise UnauthorizedError("Token workspace is missing.")
    return workspace_id


def require_role(*allowed: str):
    def dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise UnauthorizedError("Insufficient role.")
        return user

    return dep
