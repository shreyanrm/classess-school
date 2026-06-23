"""Parent partnership: a cross-context read without consent is DENIED;
surveillance is refused even with consent; the framing is partnership + pride."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.config import CommunicationSettings
from app.parent_partnership import (
    ConsentError,
    ConsentGrant,
    ParentPartnership,
    SurveillancePurposeError,
)


PARENT = "9999aaaa-0000-4000-8000-00000000000a"
CHILD = "9999aaaa-0000-4000-8000-00000000000b"
CONSENT = "cccccccc-0000-4000-8000-000000000003"


def _surface() -> ParentPartnership:
    return ParentPartnership(CommunicationSettings())


def _grant(purpose: str = "partnership_summary", *, expires_at: str | None = None) -> ConsentGrant:
    return ConsentGrant(
        consent_ref=CONSENT,
        child_uuid=CHILD,
        parent_uuid=PARENT,
        purpose=purpose,
        granted=True,
        expires_at=expires_at,
    )


def test_cross_context_read_without_consent_is_denied():
    with pytest.raises(ConsentError):
        _surface().read_child_context(
            parent_uuid=PARENT,
            child_uuid=CHILD,
            purpose="partnership_summary",
            consent=None,  # no consent -> fail-closed.
        )


def test_revoked_or_ungranted_consent_is_denied():
    revoked = ConsentGrant(
        consent_ref=CONSENT, child_uuid=CHILD, parent_uuid=PARENT,
        purpose="partnership_summary", granted=False,
    )
    with pytest.raises(ConsentError):
        _surface().read_child_context(
            parent_uuid=PARENT, child_uuid=CHILD,
            purpose="partnership_summary", consent=revoked,
        )


def test_consent_for_a_different_child_is_denied():
    grant = ConsentGrant(
        consent_ref=CONSENT, child_uuid="someone-else", parent_uuid=PARENT,
        purpose="partnership_summary", granted=True,
    )
    with pytest.raises(ConsentError):
        _surface().read_child_context(
            parent_uuid=PARENT, child_uuid=CHILD,
            purpose="partnership_summary", consent=grant,
        )


def test_expired_consent_is_denied():
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    with pytest.raises(ConsentError):
        _surface().read_child_context(
            parent_uuid=PARENT, child_uuid=CHILD,
            purpose="partnership_summary", consent=_grant(expires_at=past),
        )


def test_surveillance_purpose_is_refused_even_with_consent():
    grant = ConsentGrant(
        consent_ref=CONSENT, child_uuid=CHILD, parent_uuid=PARENT,
        purpose="live_location", granted=True,
    )
    with pytest.raises(SurveillancePurposeError):
        _surface().read_child_context(
            parent_uuid=PARENT, child_uuid=CHILD,
            purpose="live_location", consent=grant,
        )


def test_unknown_purpose_is_refused():
    with pytest.raises(SurveillancePurposeError):
        _surface().read_child_context(
            parent_uuid=PARENT, child_uuid=CHILD,
            purpose="something_made_up", consent=_grant(purpose="something_made_up"),
        )


def test_valid_consent_returns_partnership_and_pride_framing():
    card = _surface().read_child_context(
        parent_uuid=PARENT, child_uuid=CHILD,
        purpose="partnership_summary", consent=_grant(),
    )
    assert card.framing == "partnership_and_pride"
    assert card.read_under_consent_ref == CONSENT
    assert card.one_thing_to_try  # a concrete thing to do together.
    assert "why" in card.why_you_see_this.lower() or "because" in card.why_you_see_this.lower()
    # Never surveillance: the explainability says so.
    assert "monitoring" in card.why_you_see_this.lower() or "never" in card.why_you_see_this.lower()


def test_card_carries_no_raw_number_or_formula():
    card = _surface().read_child_context(
        parent_uuid=PARENT, child_uuid=CHILD,
        purpose="celebrate_progress", consent=_grant(purpose="celebrate_progress"),
    )
    blob = " ".join([card.headline, card.a_genuine_win, card.one_thing_to_try])
    assert "%" not in blob
    assert not any(ch.isdigit() for ch in blob)
