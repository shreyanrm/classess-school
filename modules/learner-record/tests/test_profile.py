"""The evidence-linked profile: plain language (no number), gated, every item
links to evidence, independent vs support-dependent foregrounded."""

from __future__ import annotations

import re

import pytest

from app.access import ConsentDenied, ConsentGrant, ReadRequest
from app.profile import (
    EvidenceSource,
    GapNote,
    GovernedTopicView,
    LearnerRecordProfile,
    assert_plain_language,
    compose_profile,
    independence_state_of,
)

from .conftest import (
    CONSENT,
    EVENT_1,
    EVENT_2,
    LEARNER_A,
    OUTSIDER,
    T_FRACTIONS,
    T_GEOMETRY,
    TEACHER,
)

_NUMBER_OR_FORMULA = re.compile(r"[0-9]|%|=|\^")


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


def _views():
    return [
        GovernedTopicView(
            topic_id=T_FRACTIONS,
            band="independent",
            source_event_ids=(EVENT_1, EVENT_2),
            observation_count=4,
        ),
        GovernedTopicView(
            topic_id=T_GEOMETRY,
            band="developing",
            source_event_ids=(EVENT_1,),
            observation_count=2,
        ),
    ]


def test_read_without_consent_is_denied():
    # A profile read without a satisfied consent check is denied — nothing built.
    with pytest.raises(ConsentDenied):
        compose_profile(_views(), request=_req(viewer=OUTSIDER), grants=[_grant()])


def test_compose_is_gated_and_returns_profile():
    profile = compose_profile(_views(), request=_req(), grants=[_grant()])
    assert isinstance(profile, LearnerRecordProfile)
    assert profile.subject == LEARNER_A
    assert len(profile.items) == 2


def test_plain_language_never_leaks_a_number_or_formula():
    profile = compose_profile(_views(), request=_req(), grants=[_grant()])
    for item in profile.items:
        assert not _NUMBER_OR_FORMULA.search(item.plain_language), item.plain_language
        for gap in item.gaps:
            assert not _NUMBER_OR_FORMULA.search(gap.plain_language)


def test_independent_vs_support_dependent_foregrounded():
    profile = compose_profile(_views(), request=_req(), grants=[_grant()])
    indep = profile.independent_topics
    supp = profile.support_dependent_topics
    assert [i.topic_id for i in indep] == [T_FRACTIONS]
    assert [i.topic_id for i in supp] == [T_GEOMETRY]
    # The record speaks in independence, never a score.
    assert profile.item(T_FRACTIONS).independence == "independent"
    assert profile.item(T_GEOMETRY).independence == "support-dependent"


def test_every_item_links_to_evidence():
    profile = compose_profile(_views(), request=_req(), grants=[_grant()])
    for item in profile.items:
        assert item.source.source_event_ids  # non-empty lineage on every item


def test_every_item_carries_permission_controls():
    profile = compose_profile(_views(), request=_req(), grants=[_grant()])
    for item in profile.items:
        assert item.permissions.consent_id == CONSENT
        assert item.permissions.learner_controlled is True
        assert item.permissions.why_visible  # the "why am I seeing this" text
        assert not _NUMBER_OR_FORMULA.search(item.permissions.why_visible)


def test_evidence_source_requires_lineage():
    with pytest.raises(ValueError):
        EvidenceSource(source_event_ids=(), last_evidence_at=None, observation_count=0)


def test_gap_note_rejects_a_number():
    with pytest.raises(ValueError):
        GapNote(
            gap_type="retention",
            plain_language="revision is 80% due",
            confirmed=True,
            source_event_ids=(EVENT_1,),
        )


def test_gap_note_requires_lineage():
    with pytest.raises(ValueError):
        GapNote(
            gap_type="retention",
            plain_language="revision is due",
            confirmed=True,
            source_event_ids=(),
        )


def test_assert_plain_language_rejects_numbers_and_formula():
    with pytest.raises(ValueError):
        assert_plain_language("scored 7 out of 10")
    with pytest.raises(ValueError):
        assert_plain_language("mastery = product of dimensions")
    # A clean sentence passes unchanged.
    assert assert_plain_language("can do this on their own") == "can do this on their own"


def test_independence_state_mapping():
    assert independence_state_of("independent") == "independent"
    assert independence_state_of("not-started") == "not-started"
    for band in ("emerging", "developing", "secure"):
        assert independence_state_of(band) == "support-dependent"


def test_profile_item_has_no_score_field():
    profile = compose_profile(_views(), request=_req(), grants=[_grant()])
    item = profile.item(T_FRACTIONS)
    # No composite / score / number field exists on the School-facing item.
    for forbidden in ("composite", "score", "mastery_number", "value"):
        assert not hasattr(item, forbidden)
