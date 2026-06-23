"""Multi-channel delivery: only SCREENED, clean, approved messages route to a
channel; flagged messages never broadcast; degrades to an in-memory outbox."""

from __future__ import annotations

import pytest

from app.config import CommunicationSettings
from app.delivery import (
    ApprovalRequiredError,
    Channel,
    DeliveryRouter,
    FlaggedDeliveryError,
)
from app.safeguarding import Safeguard


SENDER = "9999aaaa-0000-4000-8000-000000000010"
READER = "9999aaaa-0000-4000-8000-000000000011"


def _router() -> DeliveryRouter:
    return DeliveryRouter(CommunicationSettings())  # nothing wired -> outbox.


def _guard() -> Safeguard:
    return Safeguard(CommunicationSettings())


def test_clean_message_routes_to_every_channel_via_outbox():
    router = _router()
    finding = _guard().classify("Reminder: the project is due Friday.")
    for channel in Channel:
        prepared = router.prepare(
            channel=channel, recipient_ref=READER, sender_ref=SENDER,
            body="Reminder: the project is due Friday.", finding=finding,
        )
        receipt = router.deliver(prepared)
        # Degraded: recorded in the outbox, transmitted nowhere externally.
        assert receipt.delivered is False
        assert receipt.channel is channel
        assert router.adapter(channel).outbox()  # the send intent is recorded.


def test_flagged_message_is_never_prepared_or_delivered():
    router = _router()
    finding = _guard().classify("i want to die")
    assert finding.flagged is True
    with pytest.raises(FlaggedDeliveryError):
        router.prepare(
            channel=Channel.SMS, recipient_ref=READER, sender_ref=SENDER,
            body="...", finding=finding,
        )


def test_outbox_path_does_not_require_approval_but_transmits_nothing():
    # The degraded outbox fires nothing externally, so it records without
    # approval — but it is clearly not delivered.
    router = _router()
    finding = _guard().classify("See you at the meeting.")
    prepared = router.prepare(
        channel=Channel.EMAIL, recipient_ref=READER, sender_ref=SENDER,
        body="See you at the meeting.", finding=finding,
    )
    assert prepared.approved is False
    receipt = router.deliver(prepared)
    assert receipt.delivered is False


def test_a_configured_channel_requires_human_approval_to_send():
    # With a channel provider + gateway configured, a real send is consequential
    # and refuses to fire without approval (permission ladder).
    settings = CommunicationSettings(
        gateway_url="https://gateway.example",
        sms_provider_url="https://sms.example",
    )
    router = DeliveryRouter(settings)
    assert router.adapter(Channel.SMS).configured is True
    finding = Safeguard(settings).classify("Pickup at 3pm today.")
    prepared = router.prepare(
        channel=Channel.SMS, recipient_ref=READER, sender_ref=SENDER,
        body="Pickup at 3pm today.", finding=finding,
    )
    with pytest.raises(ApprovalRequiredError):
        router.deliver(prepared)


def test_provider_is_named_only_never_a_value_at_import():
    router = _router()
    for channel in Channel:
        name = router.adapter(channel).provider_env_name
        assert name.startswith("clss.communication.dev.")
        assert router.adapter(channel).configured is False  # nothing wired.
