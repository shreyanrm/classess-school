"""IEP + intervention history: human-final permission ladder, evidence-linked,
append-only, gated, plain language."""

from __future__ import annotations

import pytest

from app.access import ConsentDenied, ConsentGrant, ReadRequest
from app.iep import (
    GoalStatus,
    InterventionHistory,
    InterventionStatus,
    add_goal_progress_note,
    approve_goal,
    close_goal,
    prepare_goal_activation,
    prepare_goal_closure,
    propose_goal,
)

from .conftest import (
    CONSENT,
    EVENT_1,
    EVENT_2,
    LEARNER_A,
    OUTSIDER,
    T_FRACTIONS,
    TEACHER,
)

HUMAN = TEACHER  # opaque ref of the deciding human


def _grant(**over):
    base = dict(
        consent_id=CONSENT,
        subject=LEARNER_A,
        scopes=frozenset({"mastery-profile"}),
        purposes=frozenset({"intervention"}),
        audience=frozenset({TEACHER}),
    )
    base.update(over)
    return ConsentGrant(**base)


def _req(**over):
    base = dict(subject=LEARNER_A, viewer=TEACHER, scope="mastery-profile", purpose="intervention")
    base.update(over)
    return ReadRequest(**base)


def _goal(**over):
    base = dict(
        subject=LEARNER_A,
        topic_id=T_FRACTIONS,
        plain_language="Read a short passage and retell it in their own words.",
        source_event_ids=(EVENT_1,),
    )
    base.update(over)
    return propose_goal(**base)


def test_goal_requires_evidence():
    with pytest.raises(ValueError):
        _goal(source_event_ids=())


def test_goal_text_rejects_a_number():
    with pytest.raises(ValueError):
        _goal(plain_language="reach 80% on the next test")


def test_goal_starts_proposed_never_auto_active():
    g = _goal()
    assert g.status is GoalStatus.PROPOSED
    assert g.approved_by is None


def test_activation_is_prepared_not_fired():
    g = _goal()
    proposal = prepare_goal_activation(g, rationale="This matches the gap in the evidence.")
    assert proposal.requires_approval is True
    assert proposal.action == "iep.goal.activate"
    assert proposal.target_id == g.goal_id


def test_human_approval_activates_goal():
    g = _goal()
    prepare_goal_activation(g, rationale="The evidence supports this goal.")
    active = approve_goal(g, approved_by=HUMAN)
    assert active.status is GoalStatus.ACTIVE
    assert active.approved_by == HUMAN
    assert active.approved_at is not None


def test_approval_requires_a_human_ref():
    g = _goal()
    with pytest.raises(ValueError):
        approve_goal(g, approved_by="")


def test_progress_note_is_appended_and_evidence_linked():
    g = approve_goal(_goal(), approved_by=HUMAN)
    updated = add_goal_progress_note(
        g,
        plain_language="Is retelling shorter passages now, still needs help with longer ones.",
        source_event_ids=(EVENT_2,),
        author_role="teacher",
    )
    # Append-only: original goal is unchanged; the new goal carries the note.
    assert g.progress_notes == ()
    assert len(updated.progress_notes) == 1
    assert updated.progress_notes[0].source_event_ids == (EVENT_2,)
    assert updated.progress_notes[0].author_role == "teacher"


def test_progress_note_requires_evidence_and_plain_language():
    g = approve_goal(_goal(), approved_by=HUMAN)
    with pytest.raises(ValueError):
        add_goal_progress_note(g, plain_language="Doing better.", source_event_ids=())
    with pytest.raises(ValueError):
        add_goal_progress_note(g, plain_language="up 20%", source_event_ids=(EVENT_1,))


def test_progress_note_does_not_move_status_only_human_closes():
    g = approve_goal(_goal(), approved_by=HUMAN)
    updated = add_goal_progress_note(
        g, plain_language="Looks like they have it now.", source_event_ids=(EVENT_1,)
    )
    assert updated.status is GoalStatus.ACTIVE  # never auto-met


def test_goal_closure_is_prepared_not_fired():
    g = approve_goal(_goal(), approved_by=HUMAN)
    proposal = prepare_goal_closure(
        g, outcome=GoalStatus.MET, rationale="The evidence shows this is now independent."
    )
    assert proposal.requires_approval is True
    assert proposal.action == "iep.goal.met"
    assert proposal.target_id == g.goal_id


def test_human_closes_goal_to_met_with_attribution():
    g = approve_goal(_goal(), approved_by=HUMAN)
    prepare_goal_closure(g, outcome=GoalStatus.MET, rationale="Now retells without help.")
    closed = close_goal(g, outcome=GoalStatus.MET, closed_by=HUMAN)
    assert closed.status is GoalStatus.MET
    assert closed.closed_by == HUMAN
    assert closed.closed_at is not None


def test_goal_can_be_withdrawn_by_human():
    g = approve_goal(_goal(), approved_by=HUMAN)
    closed = close_goal(g, outcome=GoalStatus.WITHDRAWN, closed_by=HUMAN)
    assert closed.status is GoalStatus.WITHDRAWN


def test_goal_closure_requires_active_outcome_and_human_ref():
    proposed = _goal()  # not yet active
    with pytest.raises(ValueError):
        prepare_goal_closure(proposed, outcome=GoalStatus.MET, rationale="too early")
    active = approve_goal(_goal(), approved_by=HUMAN)
    with pytest.raises(ValueError):
        prepare_goal_closure(active, outcome=GoalStatus.ACTIVE, rationale="not a closure")
    with pytest.raises(ValueError):
        close_goal(active, outcome=GoalStatus.MET, closed_by="")


def test_no_progress_note_on_a_closed_goal():
    g = approve_goal(_goal(), approved_by=HUMAN)
    met = close_goal(g, outcome=GoalStatus.MET, closed_by=HUMAN)
    with pytest.raises(ValueError):
        add_goal_progress_note(met, plain_language="More progress.", source_event_ids=(EVENT_1,))


def test_intervention_recorded_proposed_and_evidence_linked():
    h = InterventionHistory(LEARNER_A)
    rec = h.record(
        plain_language="Small-group practice twice a week.",
        source_event_ids=(EVENT_1, EVENT_2),
    )
    assert rec.status is InterventionStatus.PROPOSED
    assert rec.source_event_ids == (EVENT_1, EVENT_2)


def test_intervention_requires_evidence():
    h = InterventionHistory(LEARNER_A)
    with pytest.raises(ValueError):
        h.record(plain_language="A plan with no evidence.", source_event_ids=())


def test_closing_is_prepared_then_human_final_and_append_only():
    h = InterventionHistory(LEARNER_A)
    rec = h.record(
        plain_language="Paired reading sessions.",
        source_event_ids=(EVENT_1,),
        status=InterventionStatus.ACTIVE,
    )
    proposal = h.prepare_closure(rec.intervention_id, rationale="Goal looks met in the evidence.")
    assert proposal.requires_approval is True
    assert proposal.action == "iep.intervention.close"

    closed = h.close(
        rec.intervention_id,
        outcome_note="Now retells the passage without help.",
        closed_by=HUMAN,
    )
    assert closed.status is InterventionStatus.CLOSED
    assert closed.closed_at is not None
    # Append-only: the open record is still present; current() shows latest state.
    assert len(h.all()) == 2
    current = h.current()
    assert len(current) == 1
    assert current[0].status is InterventionStatus.CLOSED


def test_close_requires_a_human_ref():
    h = InterventionHistory(LEARNER_A)
    rec = h.record(plain_language="Plan.", source_event_ids=(EVENT_1,))
    with pytest.raises(ValueError):
        h.close(rec.intervention_id, outcome_note="done", closed_by="")


def test_history_gated_view_denied_by_default():
    h = InterventionHistory(LEARNER_A)
    h.record(plain_language="Plan.", source_event_ids=(EVENT_1,))
    with pytest.raises(ConsentDenied):
        h.gated_view(request=_req(viewer=OUTSIDER), grants=[_grant()])


def test_history_gated_view_returns_timeline_when_consented():
    h = InterventionHistory(LEARNER_A)
    h.record(plain_language="First plan.", source_event_ids=(EVENT_1,))
    h.record(plain_language="Second plan.", source_event_ids=(EVENT_2,))
    view = h.gated_view(request=_req(), grants=[_grant()])
    assert len(view) == 2
