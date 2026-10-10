from __future__ import annotations

from dataclasses import dataclass

# --- Proposal brand presets ----------------------------------------------
#
# Each preset is the "Proposal & Quotation" page of a client operations kit,
# reduced to data: identity, colour tokens and the default commercial copy.
# The document itself is rendered by the web app from these values, so the
# preview a salesperson approves and the PDF a client receives come from
# one definition. Presets are code, not rows: a brand is a reviewed design
# decision, not something a model or a form can invent at runtime.


@dataclass(frozen=True, slots=True)
class MilestoneTemplate:
    title: str
    description: str
    share_pct: int


@dataclass(frozen=True, slots=True)
class BrandPreset:
    key: str
    name: str
    tagline: str
    mark: str
    #: "square" (Yusuf Jojeh kit) or "hex" (HexaTerminal kit).
    mark_shape: str
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


_STANDARD_MILESTONES_DESCRIPTIONS = (
    "Workflow mapping, requirements, domain model, contracts, delivery plan.",
    "Backend, APIs, business rules, integrations, staging and tests.",
    "UAT fixes, production release, runbook and handover.",
)

YUSUF_JOJEH = BrandPreset(
    key="yusuf_jojeh",
    name="Yusuf Jojeh",
    tagline="Backend & Business Systems Engineer",
    mark="YJ",
    mark_shape="square",
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
    default_milestones=(
        MilestoneTemplate("Discovery & System Design", _STANDARD_MILESTONES_DESCRIPTIONS[0], 20),
        MilestoneTemplate(
            "Core Engineering & Integrations", _STANDARD_MILESTONES_DESCRIPTIONS[1], 45
        ),
        MilestoneTemplate("UAT, Launch & Handover", _STANDARD_MILESTONES_DESCRIPTIONS[2], 35),
    ),
)

HEXATERMINAL = BrandPreset(
    key="hexaterminal",
    name="HexaTerminal",
    tagline="Production Systems Engineering",
    mark=">_",
    mark_shape="hex",
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
    default_milestones=(
        MilestoneTemplate("Discovery & System Design", _STANDARD_MILESTONES_DESCRIPTIONS[0], 20),
        MilestoneTemplate(
            "Core Engineering & Integrations", _STANDARD_MILESTONES_DESCRIPTIONS[1], 45
        ),
        MilestoneTemplate("UAT, Launch & Handover", _STANDARD_MILESTONES_DESCRIPTIONS[2], 35),
    ),
)

BRAND_PRESETS: dict[str, BrandPreset] = {
    preset.key: preset for preset in (YUSUF_JOJEH, HEXATERMINAL)
}
BRAND_KEYS: tuple[str, ...] = tuple(BRAND_PRESETS)
DEFAULT_BRAND_KEY = HEXATERMINAL.key


def get_brand(key: str) -> BrandPreset | None:
    return BRAND_PRESETS.get(key)
