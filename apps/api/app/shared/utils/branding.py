from __future__ import annotations

_LOGO_TEMPLATE = "https://logo.clearbit.com/{domain}"


def normalize_domain(value: str | None) -> str | None:
    """Reduce a website URL or host to a bare registrable domain.

    Returns ``None`` when no usable host can be extracted.
    """
    if not value:
        return None
    host = value.strip().lower()
    for prefix in ("https://", "http://"):
        if host.startswith(prefix):
            host = host[len(prefix) :]
    host = host.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    if host.startswith("www."):
        host = host[4:]
    host = host.strip().strip(".")
    if not host or "." not in host:
        return None
    return host


def derive_logo_url(website_domain: str | None, website_url: str | None = None) -> str | None:
    """Build a deterministic logo URL from a lead's domain.

    Uses Clearbit's public logo endpoint, which resolves a brand logo from a
    domain without an API key. Returns ``None`` when no domain is available.
    """
    domain = normalize_domain(website_domain) or normalize_domain(website_url)
    if domain is None:
        return None
    return _LOGO_TEMPLATE.format(domain=domain)
