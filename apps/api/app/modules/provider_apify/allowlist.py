from __future__ import annotations

from app.core.config import get_settings

# The only Actor keys ResearchPlanner/ApifyService will ever accept. Nothing
# upstream -- including any LLM tool call -- can supply an Apify Actor ID
# directly; it can only name one of these keys, and this module resolves it
# to a real Actor ID from server-side configuration.
ALLOWED_ACTOR_KEYS: tuple[str, ...] = (
    "company_website_crawler",
    "business_directory_crawler",
    "social_public_profile_crawler",
    "reviews_crawler",
)


def resolve_actor_id(actor_key: str) -> str | None:
    """Resolve an allowlisted Actor key to its configured Apify Actor ID.

    Returns None when the key is unknown or when no Actor ID is configured
    for it in this deployment -- both are treated the same way by callers
    (the Actor step is simply unavailable, not an error to surface as a live
    provider failure).
    """
    if actor_key not in ALLOWED_ACTOR_KEYS:
        return None
    return get_settings().apify_actor_allowlist.get(actor_key)
