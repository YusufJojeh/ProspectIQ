from __future__ import annotations

from app.modules.users.models import Workspace

# Curated presets a workspace can pick from in Settings. This list is a
# starting point, not a restriction: `profession` is a free-form string, and
# any value not present here simply falls back to the "general" catalog.
PROFESSION_PRESETS: dict[str, str] = {
    "digital_marketing": "Digital Marketing / SEO Agency",
    "real_estate": "Real Estate",
    "recruiting": "Recruiting / Staffing",
    "consulting": "Consulting / Professional Services",
    "creative_freelance": "Creative / Freelance Services",
    "b2b_sales": "B2B Sales / Business Development",
    "general": "General Lead Generation",
}


def get_workspace_profession(workspace: Workspace | None) -> str | None:
    """Read the workspace's declared profession/industry from settings_json.

    This is a convention key (`settings_json["profession"]`), not a schema
    column: the workspace settings blob already accepts arbitrary keys via the
    existing settings API, so no migration is required to support this.
    """
    if workspace is None:
        return None
    settings = workspace.settings_json or {}
    value = settings.get("profession")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
