"""Multi-channel delivery adapters (B9) — one trigger layer, many channels.

The dossier:

  messaging service over realtime channels (chat / push / email / SMS / a
  WhatsApp-class channel) · translation · conversation-to-task routing · safety
  classifiers + escalation.

A SCREENED message is what gets routed to a channel — never raw free text. This
module is the trigger layer: a single :class:`DeliveryRouter` that fans a vetted
message out to one of several channel adapters, each of which speaks a provider
named ONLY by env-var name (INVARIANT 4). Two non-negotiables:

  1. **Nothing unscreened is ever delivered.** :meth:`DeliveryRouter.deliver`
     requires a :class:`SafetyFinding` (the child-safety verdict) and REFUSES to
     deliver anything flagged. A flagged message does not go out a channel; it is
     a safeguarding matter routed to a qualified human, never broadcast.
  2. **Degrade-safe + deterministic.** With no provider configured (its env-var
     name unset) every adapter degrades to a deterministic in-memory "outbox":
     it records the SEND INTENT and reports ``delivered=False`` so callers know
     it stayed local. It never opens a live connection and never reads a secret
     VALUE at import — the provider key is read by NAME, lazily, only on a real
     send (a path intentionally not wired while no provider exists).

PERMISSION LADDER: sending a message to a real recipient is a CONSEQUENTIAL
action. :meth:`DeliveryRouter.prepare` builds a vetted, ready-to-send
:class:`OutboundMessage` and returns it for approval; :meth:`deliver` only
proceeds for an approved message (or in the degraded outbox path, which fires
nothing externally). The router prepares; a human approves the real send.

Import-safe: no I/O, no provider, no secret value read at import.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from .config import CommunicationSettings, get_settings
from .safeguarding import SafetyFinding


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Channel(str, Enum):
    """The delivery channels B9 fans out across. The WhatsApp-class channel is a
    consumer-messaging channel modelled generically (no real brand name)."""

    CHAT = "chat"            # in-app realtime chat.
    PUSH = "push"            # device push notification.
    EMAIL = "email"          # email.
    SMS = "sms"              # text message.
    WHATSAPP_CLASS = "whatsapp_class"  # a consumer messaging channel.


# Each channel maps to the dotted NAME of the env var that would carry its
# provider config (INVARIANT 4 — names only, never a value). Absent -> degraded.
CHANNEL_PROVIDER_ENV: dict[Channel, str] = {
    Channel.CHAT: "clss.communication.dev.chat_provider_url",
    Channel.PUSH: "clss.communication.dev.push_provider_url",
    Channel.EMAIL: "clss.communication.dev.email_provider_url",
    Channel.SMS: "clss.communication.dev.sms_provider_url",
    Channel.WHATSAPP_CLASS: "clss.communication.dev.whatsapp_provider_url",
}


class UnscreenedDeliveryError(RuntimeError):
    """Raised when delivery is attempted without a child-safety verdict. Nothing
    is ever sent down a channel without first being screened."""


class FlaggedDeliveryError(RuntimeError):
    """Raised when delivery is attempted for a flagged message. A flagged message
    is a safeguarding matter for a qualified human — it is never broadcast."""


class ApprovalRequiredError(PermissionError):
    """Raised when a real send is attempted without human approval. Sending is a
    consequential action on the permission ladder."""


@dataclass(frozen=True)
class OutboundMessage:
    """A vetted, prepared message ready to be delivered to a recipient context.

    Carries opaque refs only (recipient context, sender) — never PII. The
    ``finding`` is the child-safety verdict the body was screened under; the body
    text rides here because it is being delivered (it stays out of events/logs).
    ``approved`` reflects the permission ladder: a real send needs it True.
    """

    message_id: str
    channel: Channel
    recipient_ref: str       # opaque canonical_uuid / context ref of the reader.
    sender_ref: str          # opaque canonical_uuid of the sender.
    body: str                # the screened text being delivered.
    finding: SafetyFinding   # the safety verdict the body passed.
    target_lang: str = "und"
    approved: bool = False   # permission ladder: real send needs human approval.
    prepared_at: str = field(default_factory=_now_iso)

    def approve(self) -> "OutboundMessage":
        """Return an approved copy — the human's act on the permission ladder."""
        return OutboundMessage(
            message_id=self.message_id,
            channel=self.channel,
            recipient_ref=self.recipient_ref,
            sender_ref=self.sender_ref,
            body=self.body,
            finding=self.finding,
            target_lang=self.target_lang,
            approved=True,
            prepared_at=self.prepared_at,
        )


@dataclass
class DeliveryReceipt:
    """The outcome of a delivery attempt. ``delivered`` is True only when a real
    provider accepted it through the gateway; the degraded outbox reports False so
    callers know the message stayed local."""

    message_id: str
    channel: Channel
    recipient_ref: str
    delivered: bool
    provider: str            # the provider label (degraded outbox or real).
    detail: str              # human-readable status (why degraded, etc.).
    sent_at: str = field(default_factory=_now_iso)


class ChannelAdapter(ABC):
    """The interface every channel adapter implements. Degrade-safe by contract:
    when its provider env-var NAME is unset the adapter records the send intent in
    a deterministic in-memory outbox and reports ``delivered=False``."""

    channel: Channel

    def __init__(self, settings: CommunicationSettings | None = None) -> None:
        self._settings = settings or get_settings()
        self._outbox: list[OutboundMessage] = []

    @property
    def settings(self) -> CommunicationSettings:
        return self._settings

    @property
    def provider_env_name(self) -> str:
        return CHANNEL_PROVIDER_ENV[self.channel]

    @property
    def configured(self) -> bool:
        """True only when BOTH the gateway and this channel's provider URL are
        set — every external send passes the gateway, so a provider without a
        gateway is still degraded."""
        return bool(self._settings.gateway_url) and self._provider_configured()

    @abstractmethod
    def _provider_configured(self) -> bool:
        """Whether this channel's own provider URL is set (names only)."""

    def outbox(self) -> list[OutboundMessage]:
        """A read-only snapshot of the degraded in-memory outbox."""
        return list(self._outbox)

    def send(self, message: OutboundMessage) -> DeliveryReceipt:
        """Send a vetted, approved message. Degrades to the in-memory outbox when
        no provider is configured; the real gateway path is intentionally not
        wired while no provider exists (token read by NAME at that point)."""
        if not self.configured:
            self._outbox.append(message)
            return DeliveryReceipt(
                message_id=message.message_id,
                channel=self.channel,
                recipient_ref=message.recipient_ref,
                delivered=False,
                provider=f"in-memory outbox (degraded — set: {self.provider_env_name})",
                detail=(
                    "No provider configured; the send intent is recorded locally "
                    "and nothing was transmitted externally."
                ),
            )
        raise NotImplementedError(
            f"Gateway-backed {self.channel.value} delivery is not wired yet. "
            f"Configure clss.communication.dev.gateway_url + {self.provider_env_name} "
            "and implement the gateway POST here (provider token read from the "
            "environment by NAME, never hardcoded)."
        )


class ChatAdapter(ChannelAdapter):
    channel = Channel.CHAT

    def _provider_configured(self) -> bool:
        return self._settings.chat_provider_url is not None


class PushAdapter(ChannelAdapter):
    channel = Channel.PUSH

    def _provider_configured(self) -> bool:
        return self._settings.push_provider_url is not None


class EmailAdapter(ChannelAdapter):
    channel = Channel.EMAIL

    def _provider_configured(self) -> bool:
        return self._settings.email_provider_url is not None


class SmsAdapter(ChannelAdapter):
    channel = Channel.SMS

    def _provider_configured(self) -> bool:
        return self._settings.sms_provider_url is not None


class WhatsAppClassAdapter(ChannelAdapter):
    channel = Channel.WHATSAPP_CLASS

    def _provider_configured(self) -> bool:
        return self._settings.whatsapp_provider_url is not None


_ADAPTER_TYPES: dict[Channel, type[ChannelAdapter]] = {
    Channel.CHAT: ChatAdapter,
    Channel.PUSH: PushAdapter,
    Channel.EMAIL: EmailAdapter,
    Channel.SMS: SmsAdapter,
    Channel.WHATSAPP_CLASS: WhatsAppClassAdapter,
}


class DeliveryRouter:
    """The single trigger layer: prepare (recommend) then deliver (approved).

    It owns one adapter per channel and enforces the two walls before anything
    leaves: a child-safety verdict is required and must be clean, and a real send
    requires human approval (permission ladder).
    """

    def __init__(self, settings: CommunicationSettings | None = None) -> None:
        self._settings = settings or get_settings()
        self._adapters: dict[Channel, ChannelAdapter] = {
            ch: cls(self._settings) for ch, cls in _ADAPTER_TYPES.items()
        }

    @property
    def settings(self) -> CommunicationSettings:
        return self._settings

    def adapter(self, channel: Channel) -> ChannelAdapter:
        return self._adapters[channel]

    def prepare(
        self,
        *,
        channel: Channel,
        recipient_ref: str,
        sender_ref: str,
        body: str,
        finding: SafetyFinding,
        target_lang: str = "und",
    ) -> OutboundMessage:
        """Prepare a vetted, ready-to-send message (the RECOMMEND step).

        Refuses to prepare anything unscreened or flagged — a prepared message is
        always clean. The returned message is NOT approved; a human approves it
        before a real send (permission ladder).
        """
        if finding is None:
            raise UnscreenedDeliveryError(
                "Refusing to prepare a delivery with no child-safety verdict. "
                "Every message is screened before it can be routed to a channel."
            )
        if finding.flagged:
            raise FlaggedDeliveryError(
                "Refusing to prepare delivery of a FLAGGED message. A flagged "
                "message is a safeguarding matter routed to a qualified human; it "
                "is never broadcast to a channel."
            )
        return OutboundMessage(
            message_id=str(uuid.uuid4()),
            channel=channel,
            recipient_ref=recipient_ref,
            sender_ref=sender_ref,
            body=body,
            finding=finding,
            target_lang=target_lang,
            approved=False,
        )

    def deliver(self, message: OutboundMessage) -> DeliveryReceipt:
        """Deliver an approved, vetted message down its channel.

        Re-checks both walls (defence in depth): the finding must be clean, and a
        real (configured) send requires approval. The degraded outbox path fires
        nothing externally, so it does not require approval — but it never
        delivers a flagged message.
        """
        if message.finding is None:
            raise UnscreenedDeliveryError(
                "Refusing to deliver a message with no child-safety verdict."
            )
        if message.finding.flagged:
            raise FlaggedDeliveryError(
                "Refusing to deliver a FLAGGED message down a channel."
            )
        adapter = self._adapters[message.channel]
        # A real external send is consequential — it needs approval. The degraded
        # outbox transmits nothing, so it is allowed to record the intent.
        if adapter.configured and not message.approved:
            raise ApprovalRequiredError(
                "Sending to a live channel is consequential and requires human "
                "approval. Approve the prepared message before delivery; the "
                "router prepares, a person sends."
            )
        return adapter.send(message)
