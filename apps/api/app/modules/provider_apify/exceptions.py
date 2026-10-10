from app.modules.provider_serpapi.exceptions import (
    ProviderConfigError,
    ProviderError,
    RetryableProviderError,
)


class UnknownActorError(ProviderConfigError):
    """Raised when a caller requests an Apify Actor key outside the allowlist.

    This must never be raised because of untrusted input reaching the Actor
    ID itself -- callers only ever supply an allowlisted `actor_key` string;
    this is a configuration error (unknown key, or key not wired to a real
    Actor ID for this deployment), not a runtime/user-input failure.
    """


__all__ = [
    "ProviderConfigError",
    "ProviderError",
    "RetryableProviderError",
    "UnknownActorError",
]
