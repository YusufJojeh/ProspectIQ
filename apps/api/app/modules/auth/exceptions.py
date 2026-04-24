from app.core.errors import UnauthorizedError


class InvalidCredentialsError(UnauthorizedError):
    code = "invalid_credentials"

    def __init__(self) -> None:
        super().__init__("Invalid email or password.")


class InactiveUserError(UnauthorizedError):
    code = "inactive_user"

    def __init__(self) -> None:
        super().__init__("This account is inactive. Contact your workspace administrator.")
