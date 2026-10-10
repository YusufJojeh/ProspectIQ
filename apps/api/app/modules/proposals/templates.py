from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# --- Proposal brand starter templates -------------------------------------
#
# A workspace's proposals render in that workspace's own brands (the
# `proposal_brands` table). These templates are only starting points a tenant
# copies and then makes its own: the "Proposal & Quotation" pages of the two
# client operations kits it was modelled on, plus a neutral style that takes
# the workspace's name. Nothing renders from a template directly.


@dataclass(frozen=True, slots=True)
class MilestoneTemplate:
    title: str
    description: str


@dataclass(frozen=True, slots=True)
class BrandTemplate:
    key: str
    name: str
    tagline: str
    mark: str
    #: "square", "hex" or "circle"; a logo image, when set, replaces the mark.
    mark_shape: str
    #: "sans" or "serif".
    font_style: str
    number_prefix: str
    signer_label: str
    client_signer_label: str
    footer_contact: str
    paper: str
    ink: str
    muted: str
    line: str
    accent: str
    accent_secondary: str
    background: str
    radius_px: int
    default_currency: str
    validity_days: int
    default_outcome: str
    default_commercial_notes: str
    default_validity_notes: str
    default_milestones: tuple[MilestoneTemplate, ...]


_STANDARD_MILESTONES = (
    MilestoneTemplate(
        "Discovery & System Design",
        "Workflow mapping, requirements, domain model, contracts, delivery plan.",
    ),
    MilestoneTemplate(
        "Core Engineering & Integrations",
        "Backend, APIs, business rules, integrations, staging and tests.",
    ),
    MilestoneTemplate(
        "UAT, Launch & Handover",
        "UAT fixes, production release, runbook and handover.",
    ),
)

CLASSIC = BrandTemplate(
    key="classic",
    name="",
    tagline="",
    mark="",
    mark_shape="circle",
    font_style="sans",
    number_prefix="Q",
    signer_label="",
    client_signer_label="For Client · Name / role / date",
    footer_contact="",
    paper="#FFFFFF",
    ink="#111827",
    muted="#6B7280",
    line="#E5E7EB",
    accent="#2563EB",
    accent_secondary="#0F766E",
    background="#0B1220",
    radius_px=10,
    default_currency="USD",
    validity_days=30,
    default_outcome="Describe the result the client is buying: what changes for them once this is delivered.",
    default_commercial_notes=(
        "The first payment confirms the engagement and starts delivery. Remaining invoices are "
        "issued on the milestones above. Work outside the agreed scope is quoted separately."
    ),
    default_validity_notes=(
        "This quotation is valid for 30 days. Taxes and third-party fees are excluded unless "
        "explicitly listed."
    ),
    default_milestones=(
        MilestoneTemplate("Kick-off & Planning", "Requirements, schedule and success criteria."),
        MilestoneTemplate("Delivery", "The agreed scope of work."),
        MilestoneTemplate("Review & Handover", "Final changes, sign-off and handover."),
    ),
)

YUSUF_JOJEH = BrandTemplate(
    key="yusuf_jojeh",
    name="Yusuf Jojeh",
    tagline="Backend & Business Systems Engineer",
    mark="YJ",
    mark_shape="square",
    font_style="sans",
    number_prefix="YJ-Q",
    signer_label="Yusuf Mohammad Jojeh",
    client_signer_label="Client · Name / role / date",
    footer_contact="linkedin.com/in/yusuf-jojeh",
    paper="#F5F2EA",
    ink="#151719",
    muted="#6D7379",
    line="#D8D4CB",
    accent="#E45D34",
    accent_secondary="#9CA6AF",
    background="#0A0C0F",
    radius_px=8,
    default_currency="USD",
    validity_days=30,
    default_outcome=(
        "Design and deliver a production-ready backend or business system aligned with the "
        "agreed workflow, roles, permissions, integrations, data model, operational "
        "constraints and release scope."
    ),
    default_commercial_notes=(
        "The first payment reserves the engagement and starts delivery. Remaining invoices "
        "are tied to agreed milestones. Work outside the signed Statement of Work requires "
        "a written Change Request before implementation."
    ),
    default_validity_notes=(
        "This quotation is valid for 30 days. Taxes, bank fees, paid APIs, hosting, licenses "
        "and external provider fees are excluded unless explicitly listed."
    ),
    default_milestones=_STANDARD_MILESTONES,
)

HEXATERMINAL = BrandTemplate(
    key="hexaterminal",
    name="HexaTerminal",
    tagline="Production Systems Engineering",
    mark=">_",
    mark_shape="hex",
    font_style="sans",
    number_prefix="HXT-Q",
    signer_label="For HexaTerminal · Name / role / date",
    client_signer_label="For Client · Name / role / date",
    footer_contact="sales@hexaterminal.com · www.hexaterminal.com",
    paper="#F7F8FA",
    ink="#11161D",
    muted="#687383",
    line="#D9DEE5",
    accent="#2D86FF",
    accent_secondary="#FF7A1A",
    background="#05070A",
    radius_px=12,
    default_currency="USD",
    validity_days=30,
    default_outcome=(
        "Design and deliver a production-ready software system aligned with the agreed "
        "workflow, permissions, integrations, data model and release scope."
    ),
    default_commercial_notes=(
        "20% deposit starts the project. Remaining invoices are issued on the milestones "
        "above. Work outside the signed Statement of Work requires a written Change Request "
        "before implementation."
    ),
    default_validity_notes=(
        "This quotation is valid for 30 days. Taxes, third-party subscriptions, paid APIs, "
        "hosting and external provider fees are excluded unless explicitly listed."
    ),
    default_milestones=_STANDARD_MILESTONES,
)

BRAND_TEMPLATES: dict[str, BrandTemplate] = {
    template.key: template for template in (CLASSIC, YUSUF_JOJEH, HEXATERMINAL)
}
DEFAULT_TEMPLATE_KEY = CLASSIC.key


def initials(name: str) -> str:
    words = [word for word in re.split(r"[^0-9A-Za-z]+", name) if word]
    if not words:
        return "Q"
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[1][0]).upper()


def template_values(template: BrandTemplate, workspace_name: str) -> dict[str, Any]:
    """The brand fields a new brand starts with.

    The neutral template takes its identity from the workspace; the kit
    templates keep theirs so the tenant can see the reference before
    replacing it with its own.
    """
    name = template.name or workspace_name.strip() or "My Company"
    mark = template.mark or initials(name)
    prefix = template.number_prefix
    if template.key == CLASSIC.key:
        prefix = f"{initials(name)}-Q"
    return {
        "name": name[:120],
        "tagline": template.tagline,
        "mark": mark[:4],
        "mark_shape": template.mark_shape,
        "font_style": template.font_style,
        "logo_data_url": None,
        "number_prefix": prefix,
        "signer_label": template.signer_label or f"For {name} · Name / role / date",
        "client_signer_label": template.client_signer_label,
        "footer_contact": template.footer_contact,
        "paper": template.paper,
        "ink": template.ink,
        "muted": template.muted,
        "line": template.line,
        "accent": template.accent,
        "accent_secondary": template.accent_secondary,
        "background": template.background,
        "radius_px": template.radius_px,
        "default_currency": template.default_currency,
        "validity_days": template.validity_days,
        "default_outcome": template.default_outcome,
        "default_commercial_notes": template.default_commercial_notes,
        "default_validity_notes": template.default_validity_notes,
        "default_milestones": [
            {"title": m.title, "description": m.description} for m in template.default_milestones
        ],
    }
