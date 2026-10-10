from __future__ import annotations

from typing import Literal

# --- Collection / document types ---------------------------------------
#
# Deliberately a closed set. The agent may only filter on these values, so
# a prompt-injected model cannot invent a "collection type" that widens
# what it can reach.

ICP = "icp"
SERVICES = "services"
CAPABILITIES = "capabilities"
CASE_STUDIES = "case_studies"
PORTFOLIO = "portfolio"
INDUSTRY_PLAYBOOKS = "industry_playbooks"
SALES_PLAYBOOKS = "sales_playbooks"
PAST_PROPOSALS = "past_proposals"
PROPOSAL_TEMPLATES = "proposal_templates"
WINNING_OUTREACH = "winning_outreach"
OBJECTIONS = "objections"
PRICING_GUIDANCE = "pricing_guidance"
INDUSTRY_NOTES = "industry_notes"
PRODUCT_DOCS = "product_docs"

COLLECTION_TYPES: tuple[str, ...] = (
    ICP,
    SERVICES,
    CAPABILITIES,
    CASE_STUDIES,
    PORTFOLIO,
    INDUSTRY_PLAYBOOKS,
    SALES_PLAYBOOKS,
    PAST_PROPOSALS,
    PROPOSAL_TEMPLATES,
    WINNING_OUTREACH,
    OBJECTIONS,
    PRICING_GUIDANCE,
    INDUSTRY_NOTES,
    PRODUCT_DOCS,
)

CollectionType = Literal[
    "icp",
    "services",
    "capabilities",
    "case_studies",
    "portfolio",
    "industry_playbooks",
    "sales_playbooks",
    "past_proposals",
    "proposal_templates",
    "winning_outreach",
    "objections",
    "pricing_guidance",
    "industry_notes",
    "product_docs",
]

# --- Visibility ---------------------------------------------------------
#
# The domain has no team object, so a "team" level would be an invented
# concept with no membership to enforce it against. The three levels below
# are each backed by a real, checkable fact:
#
#   workspace  -- any member of the workspace may retrieve it
#   private    -- only the document's creator may retrieve it
#   restricted -- only elevated roles (see RESTRICTED_ROLES) may retrieve it
#
# Visibility is applied inside the retrieval query. A restricted document is
# never loaded and then filtered out; it is never selected in the first
# place.

VISIBILITY_WORKSPACE = "workspace"
VISIBILITY_PRIVATE = "private"
VISIBILITY_RESTRICTED = "restricted"

VISIBILITIES: tuple[str, ...] = (
    VISIBILITY_WORKSPACE,
    VISIBILITY_PRIVATE,
    VISIBILITY_RESTRICTED,
)

Visibility = Literal["workspace", "private", "restricted"]

#: Roles permitted to retrieve VISIBILITY_RESTRICTED documents. Uses the live
#: role keys (migration 0005 renamed agency_manager -> manager); "member" is
#: deliberately absent.
RESTRICTED_ROLES: frozenset[str] = frozenset(
    {"platform_admin", "account_owner", "admin", "manager"}
)

# --- Document status ----------------------------------------------------

STATUS_DRAFT = "draft"
STATUS_INGESTING = "ingesting"
STATUS_READY = "ready"
STATUS_FAILED = "failed"
STATUS_ARCHIVED = "archived"

#: The only status whose chunks may be returned by retrieval.
RETRIEVABLE_STATUSES: frozenset[str] = frozenset({STATUS_READY})


__all__ = [
    "CAPABILITIES",
    "CASE_STUDIES",
    "COLLECTION_TYPES",
    "ICP",
    "INDUSTRY_NOTES",
    "INDUSTRY_PLAYBOOKS",
    "OBJECTIONS",
    "PAST_PROPOSALS",
    "PORTFOLIO",
    "PRICING_GUIDANCE",
    "PRODUCT_DOCS",
    "PROPOSAL_TEMPLATES",
    "RESTRICTED_ROLES",
    "RETRIEVABLE_STATUSES",
    "SALES_PLAYBOOKS",
    "SERVICES",
    "STATUS_ARCHIVED",
    "STATUS_DRAFT",
    "STATUS_FAILED",
    "STATUS_INGESTING",
    "STATUS_READY",
    "VISIBILITIES",
    "VISIBILITY_PRIVATE",
    "VISIBILITY_RESTRICTED",
    "VISIBILITY_WORKSPACE",
    "WINNING_OUTREACH",
    "CollectionType",
    "Visibility",
]
