# Kept for backward compatibility: this was previously the single, hardcoded
# service catalog for every workspace. It is now also the "digital_marketing"
# preset in PROFESSION_SERVICE_CATALOGS below.
ALLOWED_SERVICE_CATALOG: tuple[str, ...] = (
    "Google Business Profile Optimization",
    "Local SEO Sprint",
    "Website Refresh",
    "Conversion Landing Page Build",
    "Review Generation and Reputation Management",
    "Call Tracking and Analytics Setup",
    "Paid Search Audit",
)

# Starter service/offer catalogs, keyed by the workspace's declared profession
# (see app.shared.utils.workspace_profile.get_workspace_profession). These are
# only ever used as the *default* catalog for a workspace that has not
# configured its own service catalog via the admin UI — any workspace can
# still fully customize its offered services regardless of profession.
PROFESSION_SERVICE_CATALOGS: dict[str, tuple[str, ...]] = {
    "digital_marketing": ALLOWED_SERVICE_CATALOG,
    "real_estate": (
        "Property Listing Consultation",
        "Home Valuation Report",
        "Buyer Representation Package",
        "Staging and Photography Add-on",
        "Comparative Market Analysis",
    ),
    "recruiting": (
        "Candidate Sourcing Retainer",
        "Contingency Placement",
        "Talent Pipeline Audit",
        "Employer Branding Consultation",
    ),
    "consulting": (
        "Discovery Workshop",
        "Strategy Assessment",
        "Pilot Engagement",
        "Retainer Advisory",
    ),
    "creative_freelance": (
        "Portfolio Review Call",
        "Project-Based Proposal",
        "Retainer Package",
        "Rush Delivery Add-on",
    ),
    "b2b_sales": (
        "Discovery Call",
        "Product Demo",
        "Pilot / Trial Offer",
        "Custom Proposal",
    ),
    "general": (
        "Discovery Call",
        "Custom Proposal",
        "Free Assessment",
        "Pilot Engagement",
        "Referral Partnership",
    ),
}


def get_default_service_catalog(profession: str | None) -> tuple[str, ...]:
    if profession and profession in PROFESSION_SERVICE_CATALOGS:
        return PROFESSION_SERVICE_CATALOGS[profession]
    return PROFESSION_SERVICE_CATALOGS["general"]
