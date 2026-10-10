from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.core.config import Settings, get_settings
from app.core.errors import ApiError

logger = logging.getLogger(__name__)

# --- External send gateway ------------------------------------------------
#
# This is the boundary where an action stops being reversible. Everything
# else the agent can do -- a draft, a note, a stage change, a task -- can be
# edited or undone by a human afterwards. A sent message cannot.
#
# Three things are therefore true of this module and must stay true:
#
#   1. It is OFF unless `external_send_enabled` is explicitly true. Off means
#      the tool is not described to the model, not executable, and not
#      approvable -- three independent refusals rather than one.
#
#   2. Even when on, there is NO real transport here. `_TRANSPORTS` below
#      `send` records the attempt and returns `delivered=False`. Wiring a real ESP,
#      WhatsApp Business API or LinkedIn integration is a separate, audited
#      piece of work with its own credentials, consent records, suppression
#      lists and compliance review. Shipping a plausible-looking stub that
#      silently does nothing would be worse than an explicit refusal, so the
#      result says exactly what happened.
#
#   3. The payload executed here is the payload a human approved. The gate
#      re-hashes the stored payload immediately before calling us; this
#      module never reconstructs, re-renders or "improves" the message body,
#      because then the text that went out would not be the text that was
#      read.

CHANNEL_EMAIL = "email"
CHANNEL_WHATSAPP = "whatsapp"
CHANNEL_LINKEDIN = "linkedin"

CHANNELS: frozenset[str] = frozenset({CHANNEL_EMAIL, CHANNEL_WHATSAPP, CHANNEL_LINKEDIN})

#: The outreach_status a successful send would move a message to. Kept here
#: so the state machine lives next to the thing that triggers the transition.
STATUS_SENT = "sent"


@dataclass(frozen=True, slots=True)
class SendRequest:
    channel: str
    #: The already-approved recipient. The gateway never derives a recipient
    #: from the lead record at send time: what a human approved included the
    #: destination, and looking it up again could send approved text to a
    #: different address than the one that was reviewed.
    destination: str
    subject: str | None
    body: str
    outreach_message_id: str


@dataclass(frozen=True, slots=True)
class SendResult:
    channel: str
    #: False whenever nothing actually left the building. Callers surface
    #: this verbatim; no code path may report a send as delivered because it
    #: "would have" been.
    delivered: bool
    provider: str
    detail: str
    attempted_at: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "channel": self.channel,
            "delivered": self.delivered,
            "provider": self.provider,
            "detail": self.detail,
            "attempted_at": self.attempted_at,
        }


class ExternalSendDisabledError(ApiError):
    """Raised whenever an external send is attempted while sending is off."""


@dataclass
class ExternalSendGateway:
    """The single place an outreach message could leave the platform."""

    settings: Settings = field(default_factory=get_settings)

    @property
    def enabled(self) -> bool:
        return bool(self.settings.external_send_enabled)

    def ensure_enabled(self) -> None:
        """Refuse before any work is done when sending is disabled.

        This is called by the executor both when previewing and when
        executing, so a disabled send cannot even be proposed for approval --
        an approval queue full of actions that can never run is its own kind
        of hazard.
        """
        if not self.enabled:
            raise ExternalSendDisabledError(
                "External sending is disabled for this deployment. The message was not sent "
                "and no external request was made. Enable EXTERNAL_SEND_ENABLED and configure "
                "an audited transport before using send tools."
            )

    def send(self, request: SendRequest) -> SendResult:
        self.ensure_enabled()
        if request.channel not in CHANNELS:
            raise ApiError(f"Unsupported send channel '{request.channel}'.")
        if not request.destination.strip():
            raise ApiError("An approved send must carry a destination.")
        if not request.body.strip():
            raise ApiError("An approved send must carry a message body.")

        # No transport is configured. We log the attempt for the audit trail
        # and report, honestly, that nothing was delivered.
        logger.warning(
            "external_send_attempted_without_transport",
            extra={
                "channel": request.channel,
                "outreach_message_id": request.outreach_message_id,
                "body_chars": len(request.body),
            },
        )
        return SendResult(
            channel=request.channel,
            delivered=False,
            provider="none",
            detail=(
                "External sending is enabled but no delivery transport is configured, so "
                "nothing was transmitted. This attempt is recorded for audit only."
            ),
            attempted_at=datetime.now(tz=UTC).isoformat(),
        )


__all__ = [
    "CHANNELS",
    "CHANNEL_EMAIL",
    "CHANNEL_LINKEDIN",
    "CHANNEL_WHATSAPP",
    "STATUS_SENT",
    "ExternalSendDisabledError",
    "ExternalSendGateway",
    "SendRequest",
    "SendResult",
]
