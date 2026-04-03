from app.core.errors import ApiError


class ProviderError(ApiError):
    status_code = 502
    code = "provider_error"


class ProviderConfigError(ApiError):
    status_code = 500
    code = "provider_config_error"


class RetryableProviderError(ProviderError):
    code = "retryable_provider_error"
