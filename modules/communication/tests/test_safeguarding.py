"""Safeguarding (child-safety): flags + escalates risky content, allows NO
unmonitored channel, and is fail-safe with no provider."""

from __future__ import annotations

import pytest

from app.config import CommunicationSettings
from app.safeguarding import (
    Safeguard,
    Severity,
    UnmonitoredChannelError,
    open_channel,
    worst,
)


WRITER = "9999aaaa-0000-4000-8000-000000000001"


def _guard() -> Safeguard:
    return Safeguard(CommunicationSettings())  # nothing wired -> on-device.


def test_clean_text_is_not_flagged_and_can_auto_respond():
    finding = _guard().classify("Can you help me with question three on fractions?")
    assert finding.flagged is False
    assert finding.severity is Severity.NONE
    assert finding.requires_human is False
    assert finding.can_auto_respond is True


def test_crisis_signal_is_detected_and_always_escalates_to_a_human():
    guard = _guard()
    finding, escalation = guard.screen(
        "i want to die, there is no reason to live",
        surface="companion",
        writer_ref=WRITER,
    )
    assert finding.flagged is True
    assert finding.is_crisis is True
    assert finding.severity is Severity.CRISIS
    assert finding.requires_human is True
    # A bot must NOT auto-respond to a crisis.
    assert finding.can_auto_respond is False
    # An escalation to a QUALIFIED HUMAN is always attached, pending the human.
    assert escalation is not None
    assert escalation.owner_role == "safeguarding_lead"
    assert escalation.status == "pending_human"
    assert escalation.is_crisis is True


def test_harassment_flags_and_escalates_to_a_qualified_human():
    guard = _guard()
    finding, escalation = guard.screen(
        "shut up loser, nobody likes you",
        surface="hub",
        writer_ref=WRITER,
    )
    assert finding.flagged is True
    assert finding.requires_human is True
    assert escalation is not None
    assert escalation.owner_role in {"counsellor", "safeguarding_lead"}


def test_directed_self_harm_incitement_is_treated_as_crisis():
    finding = _guard().classify("just kill yourself already")
    assert finding.is_crisis is True
    assert finding.severity is Severity.CRISIS


def test_escalation_carries_no_message_text_only_a_redacted_hint():
    guard = _guard()
    finding, escalation = guard.screen(
        "he hits me and i am scared to go home",
        surface="companion",
        writer_ref=WRITER,
    )
    assert escalation is not None
    # The escalation envelope carries a hint, the opaque writer ref, and a why —
    # but it is a finding object, not a raw transcript dump. The hint is short.
    assert len(escalation.excerpt_hint) <= 80
    assert escalation.writer_ref == WRITER


def test_cannot_escalate_a_clean_finding():
    guard = _guard()
    finding = guard.classify("hello, what is for homework?")
    with pytest.raises(ValueError):
        guard.escalate(finding, surface="hub", writer_ref=WRITER)


def test_no_unmonitored_channel_can_be_opened():
    # Opening a free-text channel with no safeguard bound is structurally refused.
    with pytest.raises(UnmonitoredChannelError):
        open_channel(surface="hub", guard=None)


def test_a_monitored_channel_screens_every_message_on_admit():
    guard = _guard()
    channel = open_channel(surface="hub", guard=guard)
    finding, escalation = channel.admit(
        "i want to die", writer_ref=WRITER
    )
    assert finding.is_crisis is True
    assert escalation is not None


def test_provider_absent_fails_safe_to_on_device_classifier():
    guard = _guard()
    # With no A7 service wired the classifier is the on-device floor — and it
    # still catches crisis signals (a missing provider never silences safety).
    assert guard.classifier_name == "on_device_lexical"
    assert guard.classify("i want to die").is_crisis is True


def test_worst_picks_the_highest_severity_in_a_thread():
    guard = _guard()
    findings = [
        guard.classify("what time is class?"),
        guard.classify("shut up loser"),
        guard.classify("i want to die"),
    ]
    assert worst(findings).severity is Severity.CRISIS
