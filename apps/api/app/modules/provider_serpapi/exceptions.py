from app.core.error_codes import ErrorCodes
from app.core.errors import ApiError


class ProviderError(ApiError):
    status_code = 502
    code = ErrorCodes.PROVIDER_ERROR


class ProviderConfigError(ApiError):
    status_code = 500
    code = ErrorCodes.PROVIDER_INVALID_CREDENTIALS


class RetryableProviderError(ProviderError):
    code = ErrorCodes.PROVIDER_ERROR
