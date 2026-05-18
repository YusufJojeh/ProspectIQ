from __future__ import annotations

import re
from typing import Annotated

from pydantic import AfterValidator, StringConstraints

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_email_address(value: str) -> str:
    normalized = value.strip().lower()
    if not _EMAIL_PATTERN.fullmatch(normalized):
        raise ValueError("value is not a valid email address.")

    local_part, domain = normalized.rsplit("@", 1)
    if (
        local_part.startswith(".")
        or local_part.endswith(".")
        or ".." in local_part
        or domain.startswith(".")
        or domain.endswith(".")
        or ".." in domain
    ):
        raise ValueError("value is not a valid email address.")

    return normalized


EmailAddress = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=3, max_length=320),
    AfterValidator(_validate_email_address),
]
