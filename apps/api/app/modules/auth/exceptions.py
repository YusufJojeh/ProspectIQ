from app.core.errors import UnauthorizedError


class InvalidCredentialsError(UnauthorizedError):
    code = "invalid_credentials"

    def __init__(self) -> None:
        super().__init__("Invalid email or password.")

