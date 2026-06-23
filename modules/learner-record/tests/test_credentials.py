"""Credentials: no key -> draft (never faked), key -> verifiable, gated export,
learner-controlled revoke, evidence-linked, plain-language statement."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.access import ConsentDenied, ConsentGrant, ReadRequest
from app.config import LearnerRecordSettings
from app.credentials import (
    CredentialClaim,
    CredentialState,
    export_portable,
    issue,
    revoke,
    verify,
)

from .conftest import CONSENT, EVENT_1, EVENT_2, LEARNER_A, OUTSIDER, T_GEOMETRY, TEACHER


def _claim(**over):
    base = dict(
        kind="independent-mastery",
        topic_id=T_GEOMETRY,
        statement="demonstrated independently",
        source_event_ids=(EVENT_1, EVENT_2),
    )
    base.update(over)
    return CredentialClaim(**base)


_NO_KEY = LearnerRecordSettings()  # nothing configured
_WITH_KEY = LearnerRecordSettings(credential_signing_key="env-supplied-key-by-name")


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
    base = dict(subject=LEARNER_A, viewer=TEACHER, scope="credentials", purpose="mastery")
    base.update(over)
    return ReadRequest(**base)


def test_claim_requires_evidence():
    with pytest.raises(ValueError):
        CredentialClaim(
            kind="independent-mastery",
            topic_id=T_GEOMETRY,
            statement="demonstrated independently",
            source_event_ids=(),
        )


def test_claim_statement_rejects_a_number():
    with pytest.raises(ValueError):
        _claim(statement="scored 90 percent")


def test_no_signing_key_issues_draft_not_verifiable():
    cred = issue(subject=LEARNER_A, claim=_claim(), settings=_NO_KEY)
    assert cred.state is CredentialState.DRAFT
    assert cred.signature is None
    assert cred.is_verifiable is False
    # Never faked: verify must say false with no key.
    assert verify(cred, settings=_NO_KEY) is False


def test_signing_key_issues_verifiable_credential():
    cred = issue(subject=LEARNER_A, claim=_claim(), settings=_WITH_KEY)
    assert cred.state is CredentialState.VERIFIED
    assert cred.signature
    assert cred.is_verifiable is True
    assert verify(cred, settings=_WITH_KEY) is True


def test_tampered_credential_fails_verification():
    cred = issue(subject=LEARNER_A, claim=_claim(), settings=_WITH_KEY)
    tampered = cred.__class__(
        credential_id=cred.credential_id,
        subject=cred.subject,
        claim=_claim(statement="demonstrated with help"),  # changed claim
        issued_at=cred.issued_at,
        state=cred.state,
        issuer=cred.issuer,
        expires_at=cred.expires_at,
        signature=cred.signature,  # old signature
    )
    assert verify(tampered, settings=_WITH_KEY) is False


def test_expired_credential_does_not_verify():
    past = datetime.now(timezone.utc) - timedelta(days=1)
    cred = issue(subject=LEARNER_A, claim=_claim(), settings=_WITH_KEY, expires_at=past)
    assert verify(cred, settings=_WITH_KEY) is False


def test_revoke_is_learner_controlled_and_not_verifiable():
    cred = issue(subject=LEARNER_A, claim=_claim(), settings=_WITH_KEY)
    revoked = revoke(cred)
    assert revoked.state is CredentialState.REVOKED
    assert verify(revoked, settings=_WITH_KEY) is False


def test_export_to_outsider_is_gated_denied():
    cred = issue(subject=LEARNER_A, claim=_claim(), settings=_WITH_KEY)
    with pytest.raises(ConsentDenied):
        export_portable(cred, request=_req(viewer=OUTSIDER), grants=[_grant()])


def test_self_export_is_portable_and_pii_free():
    cred = issue(subject=LEARNER_A, claim=_claim(), settings=_WITH_KEY)
    doc = export_portable(cred, request=_req(viewer=LEARNER_A), grants=[_grant()])
    assert doc["format"] == "classess.credential.v1"
    assert doc["verifiable"] is True
    assert doc["subject"] == LEARNER_A  # opaque only
    blob = str(doc).lower()
    assert "email" not in blob and "@" not in blob
    # Statement carries no raw score.
    assert not any(ch.isdigit() for ch in doc["claim"]["statement"])


def test_export_carries_full_evidence_lineage():
    cred = issue(subject=LEARNER_A, claim=_claim(), settings=_WITH_KEY)
    doc = export_portable(cred, request=_req(viewer=LEARNER_A), grants=[_grant()])
    assert doc["claim"]["source_event_ids"] == [EVENT_1, EVENT_2]
