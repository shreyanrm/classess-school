"""External-signal reconciliation: transport/gate vs school/classroom."""

import pytest

from app.external_signals import (
    ExternalSignal,
    Presence,
    SignalSource,
    reconcile_external,
    to_review_payload,
)


def _sig(cuid, source, presence, date="2026-06-22"):
    return ExternalSignal(cuid, source, presence, date)


def test_transport_boarded_but_not_at_school_is_conflict():
    signals = [
        _sig("uuid-a", SignalSource.TRANSPORT, Presence.OBSERVED),
        _sig("uuid-a", SignalSource.ARRIVAL, Presence.NOT_OBSERVED),
    ]
    conflicts = reconcile_external(signals)
    assert len(conflicts) == 1
    c = conflicts[0]
    assert c.upstream_source == "transport"
    assert c.downstream_source == "arrival"
    assert c.needs_human_review is True
    assert c.safeguarding_relevant is True


def test_gate_entry_but_not_in_classroom_is_conflict():
    signals = [
        _sig("uuid-b", SignalSource.GATE, Presence.OBSERVED),
        _sig("uuid-b", SignalSource.CLASSROOM, Presence.NOT_OBSERVED),
    ]
    conflicts = reconcile_external(signals)
    assert len(conflicts) == 1
    assert conflicts[0].downstream_source == "classroom"


def test_agreement_no_conflict():
    signals = [
        _sig("uuid-c", SignalSource.TRANSPORT, Presence.OBSERVED),
        _sig("uuid-c", SignalSource.ARRIVAL, Presence.OBSERVED),
    ]
    assert reconcile_external(signals) == []


def test_no_data_downstream_never_conflicts():
    # a silent downstream source is never read as absence (fail-closed)
    signals = [
        _sig("uuid-d", SignalSource.GATE, Presence.OBSERVED),
        _sig("uuid-d", SignalSource.CLASSROOM, Presence.NO_DATA),
    ]
    assert reconcile_external(signals) == []


def test_missing_downstream_signal_no_conflict():
    # only the upstream signal exists -> cannot corroborate, do not accuse
    signals = [_sig("uuid-e", SignalSource.TRANSPORT, Presence.OBSERVED)]
    assert reconcile_external(signals) == []


def test_review_payload_is_pii_free():
    signals = [
        _sig("uuid-a", SignalSource.TRANSPORT, Presence.OBSERVED),
        _sig("uuid-a", SignalSource.ARRIVAL, Presence.NOT_OBSERVED),
    ]
    payload = to_review_payload(reconcile_external(signals))
    assert payload
    for entry in payload:
        assert "@" not in entry["canonical_uuid"]
        assert entry["needs_human_review"] is True
        assert entry["rationale"]


def test_pii_signal_rejected():
    with pytest.raises(ValueError):
        ExternalSignal("kid@example.com", SignalSource.GATE, Presence.OBSERVED, "d")
