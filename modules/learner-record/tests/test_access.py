"""The consent + purpose gate: denied-by-default, scope/purpose/audience exact."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.access import (
    ConsentDenied,
    ConsentGrant,
    Decision,
    ReadRequest,
    evaluate,
    require,
)

from .conftest import CONSENT, LEARNER_A, OUTSIDER, PARENT, TEACHER


def _grant(**over):
    base = dict(
        consent_id=CONSENT,
        subject=LEARNER_A,
        scopes=frozenset({"mastery-profile"}),
        purposes=frozenset({"mastery"}),
        audience=frozenset({TEACHER}),
    )
    base.update(over)
    return ConsentGrant(**base)


def _req(**over):
    base = dict(subject=LEARNER_A, viewer=TEACHER, scope="mastery-profile", purpose="mastery")
    base.update(over)
    return ReadRequest(**base)


def test_no_grant_is_denied_by_default():
    # The core law: a read with NO recorded consent is denied, never fail-open.
    result = evaluate(_req(), grants=[])
    assert result.decision is Decision.DENY
    assert not result.allowed
    assert "No consent" in result.reason


def test_matching_grant_allows_and_names_the_consent():
    result = evaluate(_req(), grants=[_grant()])
    assert result.allowed
    assert result.consent_id == CONSENT


def test_self_read_is_always_in_audience():
    # The learner reading their own record needs no explicit audience entry.
    result = evaluate(_req(viewer=LEARNER_A), grants=[_grant(audience=frozenset())])
    assert result.allowed


def test_wrong_purpose_is_denied():
    # A grant for 'communication' does NOT satisfy a 'mastery' read.
    g = _grant(purposes=frozenset({"communication"}))
    result = evaluate(_req(purpose="mastery"), grants=[g])
    assert not result.allowed
    assert "purpose" in result.reason


def test_wrong_scope_is_denied():
    g = _grant(scopes=frozenset({"portfolio"}))
    result = evaluate(_req(scope="mastery-profile"), grants=[g])
    assert not result.allowed
    assert "mastery-profile" in result.reason


def test_viewer_not_in_audience_is_denied():
    # The Parent surface is gated like any other — no implicit surveillance.
    result = evaluate(_req(viewer=OUTSIDER), grants=[_grant()])
    assert not result.allowed
    assert "audience" in result.reason


def test_revoked_grant_is_denied():
    result = evaluate(_req(), grants=[_grant(revoked=True)])
    assert not result.allowed
    assert "revoked" in result.reason


def test_expired_grant_is_denied():
    past = datetime.now(timezone.utc) - timedelta(days=1)
    result = evaluate(_req(), grants=[_grant(expires_at=past)])
    assert not result.allowed
    assert "expired" in result.reason


def test_parent_in_audience_is_allowed():
    # Partnership: a parent the learner consented to CAN read — gated, not banned.
    g = _grant(audience=frozenset({PARENT}))
    result = evaluate(_req(viewer=PARENT), grants=[g])
    assert result.allowed


def test_require_raises_consent_denied_on_deny():
    with pytest.raises(ConsentDenied) as ei:
        require(_req(viewer=OUTSIDER), grants=[_grant()])
    assert "audience" in str(ei.value)


def test_no_pii_in_denial_reason():
    blob = evaluate(_req(), grants=[]).reason.lower()
    assert "email" not in blob and "@" not in blob
