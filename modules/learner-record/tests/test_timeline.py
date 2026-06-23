"""Continuous timeline: gated, ordered, plain-language, evidence-linked, all kinds."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.access import ConsentDenied, ConsentGrant, ReadRequest
from app.timeline import (
    AUTHOR_LEARNER,
    AUTHOR_TEACHER,
    TimelineKind,
    TimelineSignal,
    compose_timeline,
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

_T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


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


def _signals():
    # Deliberately out of order to prove the timeline sorts.
    return [
        TimelineSignal(
            kind=TimelineKind.REFLECTION,
            occurred_at=_T0 + timedelta(days=10),
            summary="I think I finally get why the steps work.",
            source_event_ids=(EVENT_2,),
            author_role=AUTHOR_LEARNER,
        ),
        TimelineSignal(
            kind=TimelineKind.MASTERY,
            occurred_at=_T0,
            summary="Can now do this on their own.",
            source_event_ids=(EVENT_1,),
            topic_id=T_FRACTIONS,
        ),
        TimelineSignal(
            kind=TimelineKind.OBSERVATION,
            occurred_at=_T0 + timedelta(days=5),
            summary="Helped a classmate explain the idea.",
            source_event_ids=(EVENT_1, EVENT_2),
            author_role=AUTHOR_TEACHER,
            topic_id=T_GEOMETRY,
        ),
    ]


def test_timeline_is_gated_denied_by_default():
    with pytest.raises(ConsentDenied):
        compose_timeline(_signals(), request=_req(viewer=OUTSIDER), grants=[_grant()])


def test_timeline_is_ordered_oldest_to_newest():
    tl = compose_timeline(_signals(), request=_req(), grants=[_grant()])
    times = [e.occurred_at for e in tl.entries]
    assert times == sorted(times)
    assert tl.entries[0].kind == TimelineKind.MASTERY


def test_timeline_carries_all_kinds_and_evidence():
    tl = compose_timeline(_signals(), request=_req(), grants=[_grant()])
    kinds = {e.kind for e in tl.entries}
    assert TimelineKind.MASTERY in kinds
    assert TimelineKind.OBSERVATION in kinds
    assert TimelineKind.REFLECTION in kinds
    for e in tl.entries:
        assert e.source_event_ids  # evidence over assertion


def test_observations_and_reflections_keep_author_role():
    tl = compose_timeline(_signals(), request=_req(), grants=[_grant()])
    assert tl.observations[0].author_role == AUTHOR_TEACHER
    assert tl.reflections[0].author_role == AUTHOR_LEARNER


def test_entry_with_no_evidence_is_refused():
    with pytest.raises(ValueError):
        TimelineSignal(
            kind=TimelineKind.MASTERY,
            occurred_at=_T0,
            summary="Did the thing.",
            source_event_ids=(),
        )
        compose_timeline(
            [
                TimelineSignal(
                    kind=TimelineKind.MASTERY,
                    occurred_at=_T0,
                    summary="Did the thing.",
                    source_event_ids=(),
                )
            ],
            request=_req(),
            grants=[_grant()],
        )


def test_plain_language_guard_rejects_a_number_in_summary():
    with pytest.raises(ValueError):
        compose_timeline(
            [
                TimelineSignal(
                    kind=TimelineKind.MASTERY,
                    occurred_at=_T0,
                    summary="scored 90%",
                    source_event_ids=(EVENT_1,),
                )
            ],
            request=_req(),
            grants=[_grant()],
        )


def test_entries_carry_permission_controls_and_why():
    tl = compose_timeline(_signals(), request=_req(), grants=[_grant()])
    perm = tl.entries[0].permissions
    assert perm.consent_id == CONSENT
    assert LEARNER_A in perm.visible_to and TEACHER in perm.visible_to
    assert perm.learner_controlled is True
    assert perm.why_visible


def test_since_filters_recent_entries():
    tl = compose_timeline(_signals(), request=_req(), grants=[_grant()])
    recent = tl.since(_T0 + timedelta(days=6))
    assert all(e.occurred_at >= _T0 + timedelta(days=6) for e in recent)
    assert len(recent) == 1
