"""Device-free card-scan check: valid/invalid codes, idempotency, no PII."""

from __future__ import annotations

import pytest

from app import events
from app.device_free_check import (
    CheckOutcome,
    DeviceFreeCheck,
    ScanCard,
    is_valid_scan_code,
)


def _uuid() -> str:
    return events.new_canonical_uuid()


def _card(uuid_str=None) -> ScanCard:
    return ScanCard(code="CLSS-AB12-CD34-EF56", subject_uuid=uuid_str or _uuid())


def test_scan_code_format_validation():
    assert is_valid_scan_code("CLSS-AB12-CD34-EF56")
    assert not is_valid_scan_code("hello")
    assert not is_valid_scan_code("CLSS-abc")


def test_card_rejects_non_opaque_subject():
    with pytest.raises(ValueError):
        ScanCard(code="CLSS-AB12-CD34-EF56", subject_uuid="Asha Rao")


def test_valid_scan_marks_present_device_free():
    chk = DeviceFreeCheck("s1")
    card = _card()
    chk.register_card(card)
    res = chk.scan(card.code)
    assert res.outcome is CheckOutcome.PRESENT_DEVICE_FREE
    assert res.is_present
    assert chk.present_count() == 1


def test_invalid_or_unknown_scan_is_not_punitive():
    chk = DeviceFreeCheck("s1")
    res = chk.scan("CLSS-ZZ99-ZZ99-ZZ99")  # not registered
    assert res.outcome is CheckOutcome.CODE_INVALID
    assert not res.is_present
    assert chk.present_count() == 0


def test_rescan_is_idempotent():
    chk = DeviceFreeCheck("s1")
    card = _card()
    chk.register_card(card)
    chk.scan(card.code)
    chk.scan(card.code)
    assert chk.present_count() == 1


def test_event_is_assistive_non_punitive_and_opaque():
    chk = DeviceFreeCheck("s1")
    card = _card()
    chk.register_card(card)
    res = chk.scan(card.code)
    ev = chk.to_event(res)
    assert ev is not None
    assert ev.subject_uuid == card.subject_uuid
    assert ev.payload["assistive"] is True
    assert ev.payload["punitive"] is False


def test_invalid_scan_produces_no_person_event():
    chk = DeviceFreeCheck("s1")
    res = chk.scan("CLSS-ZZ99-ZZ99-ZZ99")
    assert chk.to_event(res) is None
