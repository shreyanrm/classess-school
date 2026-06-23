"""Child-safety + PII screening on free-text surfaces."""

from app.safety import (
    assert_no_pii_identifier,
    screen_free_text,
)

import pytest


def test_clean_text_ok():
    r = screen_free_text("Was at the dentist this morning.")
    assert r.ok is True
    assert r.needs_human_review is False
    assert r.sanitized == "Was at the dentist this morning."


def test_phone_redacted():
    r = screen_free_text("call guardian on +1 555 123 4567")
    assert "phone" in r.pii_findings
    assert "+1 555 123 4567" not in r.sanitized


def test_email_redacted():
    r = screen_free_text("email parent@example.com")
    assert "email" in r.pii_findings
    assert "@" not in r.sanitized


def test_child_safety_marker_routes_to_review():
    r = screen_free_text("the child said they want to die")
    assert r.needs_human_review is True
    assert r.ok is False
    assert r.safety_findings


def test_none_is_ok():
    r = screen_free_text(None)
    assert r.ok is True
    assert r.sanitized == ""


def test_too_long_rejected():
    r = screen_free_text("x" * 1000)
    assert r.ok is False


def test_assert_no_pii_identifier_rejects_email_and_phone():
    with pytest.raises(ValueError):
        assert_no_pii_identifier("a@b.com")
    with pytest.raises(ValueError):
        assert_no_pii_identifier("+1 555 123 4567")


def test_assert_no_pii_identifier_allows_uuid():
    # opaque uuid passes
    assert_no_pii_identifier("uuid-1234-abcd")
