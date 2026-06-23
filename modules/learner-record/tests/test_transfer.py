"""Portable record handoff: learner-controlled (requires_approval), gated export,
revocable, PII-free, verifiability never faked."""

from __future__ import annotations

import pytest

from app.access import ConsentDenied, ConsentGrant, ReadRequest
from app.artifacts import issue_badge, issue_certificate
from app.config import LearnerRecordSettings
from app.credentials import CredentialClaim, issue
from app.transfer import (
    HandoffState,
    authorize_handoff,
    export_handoff,
    prepare_handoff,
    revoke_handoff,
)

from .conftest import CONSENT, EVENT_1, EVENT_2, LEARNER_A, OUTSIDER, T_GEOMETRY, TEACHER

_NO_KEY = LearnerRecordSettings()
_WITH_KEY = LearnerRecordSettings(credential_signing_key="env-supplied-key-by-name")

# An opaque id for a permitted destination context (e.g. a next school).
NEXT_CONTEXT = "context://next-school/opaque-1"
HUMAN = LEARNER_A  # the learner authorizes their own handoff


def _claim(**over):
    base = dict(
        kind="course-completion",
        topic_id=T_GEOMETRY,
        statement="completed the course independently",
        source_event_ids=(EVENT_1, EVENT_2),
    )
    base.update(over)
    return CredentialClaim(**base)


def _cred(settings=_WITH_KEY, **over):
    return issue(subject=LEARNER_A, claim=_claim(**over), settings=settings)


def _grant(**over):
    base = dict(
        consent_id=CONSENT,
        subject=LEARNER_A,
        scopes=frozenset({"credentials"}),
        purposes=frozenset({"mastery"}),
        audience=frozenset({TEACHER}),
    )
    base.update(over)
    return ConsentGrant(**base)


def _req(**over):
    base = dict(subject=LEARNER_A, viewer=LEARNER_A, scope="credentials", purpose="mastery")
    base.update(over)
    return ReadRequest(**base)


def _items():
    return (
        _cred(),
        issue_certificate(credential=_cred(), title="Course of study completed"),
        issue_badge(credential=_cred(), title="Independent problem solver", emblem_ref="ref://e/1"),
    )


def test_handoff_requires_at_least_one_item():
    with pytest.raises(ValueError):
        prepare_handoff(
            subject=LEARNER_A, recipient_context=NEXT_CONTEXT, items=[], rationale="empty"
        )


def test_handoff_only_carries_holders_own_items():
    foreign = issue(subject=OUTSIDER, claim=_claim(), settings=_WITH_KEY)
    with pytest.raises(ValueError):
        prepare_handoff(
            subject=LEARNER_A,
            recipient_context=NEXT_CONTEXT,
            items=[foreign],
            rationale="not the holder's record",
        )


def test_prepare_is_proposal_not_fired():
    handoff, proposal = prepare_handoff(
        subject=LEARNER_A,
        recipient_context=NEXT_CONTEXT,
        items=_items(),
        rationale="Sharing my record with the next school.",
    )
    assert handoff.state is HandoffState.PROPOSED
    assert proposal.requires_approval is True
    assert proposal.item_count == 3
    assert proposal.handoff_id == handoff.handoff_id


def test_proposed_handoff_cannot_export():
    handoff, _ = prepare_handoff(
        subject=LEARNER_A, recipient_context=NEXT_CONTEXT, items=_items(), rationale="r"
    )
    with pytest.raises(PermissionError):
        export_handoff(handoff, request=_req(), grants=[_grant()])


def test_authorize_requires_human_ref_and_proposed_state():
    handoff, _ = prepare_handoff(
        subject=LEARNER_A, recipient_context=NEXT_CONTEXT, items=_items(), rationale="r"
    )
    with pytest.raises(ValueError):
        authorize_handoff(handoff, authorized_by="")
    live = authorize_handoff(handoff, authorized_by=HUMAN)
    with pytest.raises(ValueError):
        authorize_handoff(live, authorized_by=HUMAN)  # already authorized


def test_authorized_handoff_exports_self_contained_pii_free():
    handoff, _ = prepare_handoff(
        subject=LEARNER_A, recipient_context=NEXT_CONTEXT, items=_items(), rationale="r"
    )
    live = authorize_handoff(handoff, authorized_by=HUMAN)
    doc = export_handoff(live, request=_req(), grants=[_grant()])
    assert doc["format"] == "classess.record-handoff.v1"
    assert doc["subject"] == LEARNER_A
    assert doc["recipient_context"] == NEXT_CONTEXT
    assert doc["state"] == "authorized"
    assert len(doc["items"]) == 3
    assert doc["fully_verifiable"] is True
    blob = str(doc).lower()
    assert "email" not in blob and "@" not in blob


def test_export_to_outsider_is_gated_denied():
    handoff, _ = prepare_handoff(
        subject=LEARNER_A, recipient_context=NEXT_CONTEXT, items=_items(), rationale="r"
    )
    live = authorize_handoff(handoff, authorized_by=HUMAN)
    with pytest.raises(ConsentDenied):
        export_handoff(live, request=_req(viewer=OUTSIDER), grants=[_grant()])


def test_revoked_handoff_refuses_export():
    handoff, _ = prepare_handoff(
        subject=LEARNER_A, recipient_context=NEXT_CONTEXT, items=_items(), rationale="r"
    )
    live = authorize_handoff(handoff, authorized_by=HUMAN)
    revoked = revoke_handoff(live)
    assert revoked.state is HandoffState.REVOKED
    with pytest.raises(PermissionError):
        export_handoff(revoked, request=_req(), grants=[_grant()])


def test_unsigned_items_travel_as_not_fully_verifiable_never_faked():
    draft_cred = _cred(settings=_NO_KEY)
    handoff, _ = prepare_handoff(
        subject=LEARNER_A,
        recipient_context=NEXT_CONTEXT,
        items=[draft_cred],
        rationale="r",
    )
    live = authorize_handoff(handoff, authorized_by=HUMAN)
    assert live.fully_verifiable is False
    doc = export_handoff(live, request=_req(), grants=[_grant()])
    assert doc["fully_verifiable"] is False
    assert doc["items"][0]["verifiable"] is False
