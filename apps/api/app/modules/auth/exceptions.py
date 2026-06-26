from app.core.error_codes import ErrorCodes
from app.core.errors import UnauthorizedError


class InvalidCredentialsError(UnauthorizedError):
    code = ErrorCodes.INVALID_CREDENTIALS

    def __init__(self) -> None:
        super().__init__("Invalid email or password.")


class InactiveUserError(UnauthorizedError):
    code = ErrorCodes.USER_INACTIVE

    def __init__(self) -> None:
        super().__init__("This account is inactive. Contact your workspace administrator.")


class InactiveWorkspaceError(UnauthorizedError):
    code = ErrorCodes.WORKSPACE_INACTIVE

    def __init__(self) -> None:
        super().__init__("This workspace is inactive. Contact platform support.")
