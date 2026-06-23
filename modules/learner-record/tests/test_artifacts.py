"""Certificate + badge artifacts: distinct types, verifiability inherited (never
faked), PII-free, gated export, plain-language title."""

from __future__ import annotations

import pytest

from app.access import ConsentDenied, ConsentGrant, ReadRequest
from app.artifacts import (
    ArtifactType,
    Badge,
    Certificate,
    export_artifact,
    issue_badge,
    issue_certificate,
)
from app.config import LearnerRecordSettings
from app.credentials import CredentialClaim, issue

from .conftest import CONSENT, EVENT_1, EVENT_2, LEARNER_A, OUTSIDER, T_GEOMETRY, TEACHER

_NO_KEY = LearnerRecordSettings()
_WITH_KEY = LearnerRecordSettings(credential_signing_key="env-supplied-key-by-name")


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
    base = dict(subject=LEARNER_A, viewer=TEACHER, scope="credentials", purpose="mastery")
    base.update(over)
    return ReadRequest(**base)


def test_certificate_and_badge_are_distinct_types():
    cert = issue_certificate(credential=_cred(), title="Course of study completed")
    badge = issue_badge(credential=_cred(), title="Independent problem solver", emblem_ref="ref://emblem/1")
    assert cert.artifact_type is ArtifactType.CERTIFICATE
    assert badge.artifact_type is ArtifactType.BADGE
    assert badge.emblem_ref == "ref://emblem/1"


def test_verifiability_inherited_from_signed_credential():
    cert = issue_certificate(credential=_cred(settings=_WITH_KEY), title="Course completed")
    assert cert.is_verifiable is True


def test_unsigned_credential_yields_non_verifiable_artifact_never_faked():
    cert = issue_certificate(credential=_cred(settings=_NO_KEY), title="Course completed")
    badge = issue_badge(credential=_cred(settings=_NO_KEY), title="A skill")
    assert cert.is_verifiable is False
    assert badge.is_verifiable is False


def test_title_rejects_a_raw_score():
    with pytest.raises(ValueError):
        issue_certificate(credential=_cred(), title="scored 100")


def test_artifact_subject_must_match_credential():
    cred = _cred()
    with pytest.raises(ValueError):
        Certificate(
            artifact_id="a1",
            artifact_type=ArtifactType.CERTIFICATE,
            subject=OUTSIDER,  # mismatched
            title="Course completed",
            credential=cred,
            issued_at=cred.issued_at,
        )


def test_wrong_type_on_dataclass_is_refused():
    cred = _cred()
    with pytest.raises(ValueError):
        Badge(
            artifact_id="b1",
            artifact_type=ArtifactType.CERTIFICATE,  # wrong for a Badge
            subject=LEARNER_A,
            title="A skill",
            credential=cred,
            issued_at=cred.issued_at,
        )


def test_export_to_outsider_is_gated_denied():
    cert = issue_certificate(credential=_cred(), title="Course completed")
    with pytest.raises(ConsentDenied):
        export_artifact(cert, request=_req(viewer=OUTSIDER), grants=[_grant()])


def test_self_export_is_portable_pii_free_and_carries_credential():
    badge = issue_badge(credential=_cred(), title="Independent problem solver", emblem_ref="ref://e/9")
    doc = export_artifact(badge, request=_req(viewer=LEARNER_A), grants=[_grant()])
    assert doc["format"] == "classess.artifact.v1"
    assert doc["artifact_type"] == "badge"
    assert doc["subject"] == LEARNER_A
    assert doc["emblem_ref"] == "ref://e/9"
    assert doc["credential"]["format"] == "classess.credential.v1"
    assert doc["verifiable"] is True
    blob = str(doc).lower()
    assert "email" not in blob and "@" not in blob


def test_unsigned_export_reports_not_verifiable():
    cert = issue_certificate(credential=_cred(settings=_NO_KEY), title="Course completed")
    doc = export_artifact(cert, request=_req(viewer=LEARNER_A), grants=[_grant()])
    assert doc["verifiable"] is False
