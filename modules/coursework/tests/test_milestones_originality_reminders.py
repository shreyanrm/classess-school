"""Group milestones, originality style-shift / source comparison /
explain-or-rewrite, and risk-based assignment reminders."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.groups import (
    Milestone,
    MilestoneStatus,
    ProjectMilestones,
    plan_milestones,
)
from app.originality import (
    ComparisonSource,
    ExplainOrRewriteAction,
    OriginalitySignal,
    ask_to_explain_or_rewrite,
    check_originality_sourced,
    detect_style_shift,
)
from app.reminders import (
    LearnerReminderState,
    ReminderUrgency,
    plan_reminders,
)


# --- milestones ----------------------------------------------------------
def test_plan_milestones_starts_pending():
    pm = plan_milestones("Team 1", ["Proposal", "Build", "Present"])
    assert len(pm.milestones) == 3
    assert all(m.status is MilestoneStatus.PENDING for m in pm.milestones)
    assert pm.progress == 0.0


def test_milestone_progress_and_advance():
    pm = plan_milestones("Team 1", ["A", "B", "C", "D"])
    reached = pm.milestones[0].advanced_to(MilestoneStatus.REACHED)
    pm2 = ProjectMilestones(group_label="Team 1", milestones=[reached, *pm.milestones[1:]])
    assert pm2.reached_count == 1
    assert pm2.progress == 0.25


def test_overdue_milestones_are_a_signal_not_reached():
    past = datetime.now(timezone.utc) - timedelta(days=1)
    pm = plan_milestones("Team 1", ["Late one"], due_dates=[past])
    overdue = pm.overdue_as_of(datetime.now(timezone.utc))
    assert len(overdue) == 1
    # Once reached, it is no longer overdue.
    pm_done = ProjectMilestones(
        group_label="Team 1", milestones=[pm.milestones[0].advanced_to(MilestoneStatus.REACHED)]
    )
    assert pm_done.overdue_as_of(datetime.now(timezone.utc)) == []


# --- originality: source comparison --------------------------------------
def test_sourced_comparison_attributes_match_to_model_answer():
    text = "the water cycle moves water through evaporation condensation and precipitation"
    res = check_originality_sourced(
        submission_ref=uuid4(),
        text=text,
        model_answers={"key": text},
        peer_corpus={"classmate": "i went to the park and played football all afternoon"},
    )
    assert res.signal is OriginalitySignal.NEEDS_REVIEW
    assert res.needs_human_review is True
    assert res.by_source.get(ComparisonSource.MODEL_ANSWER, 0.0) >= 0.65
    assert res.rung == "recommend"


def test_sourced_comparison_undetermined_with_nothing():
    res = check_originality_sourced(submission_ref=uuid4(), text="anything")
    assert res.signal is OriginalitySignal.UNDETERMINED
    assert res.needs_human_review is False


# --- originality: style shift --------------------------------------------
def test_style_shift_flags_large_change():
    res = detect_style_shift(
        submission_ref=uuid4(),
        text="Notwithstanding the aforementioned considerations, the epistemological framework necessitates rigorous interrogation.",
        baseline_texts=["i like cats. cats are soft. i pet my cat a lot."],
    )
    assert res.shifted is True
    assert res.needs_human_review is True
    assert res.rung == "recommend"


def test_style_shift_consistent_is_not_flagged():
    res = detect_style_shift(
        submission_ref=uuid4(),
        text="i like dogs. dogs are loud. i walk my dog daily.",
        baseline_texts=["i like cats. cats are soft. i pet my cat often."],
    )
    assert res.shifted is False
    assert res.needs_human_review is False


def test_style_shift_no_baseline_cannot_assess():
    res = detect_style_shift(submission_ref=uuid4(), text="some text", baseline_texts=[])
    assert res.shifted is False
    assert res.needs_human_review is False
    assert res.distance == 0.0


# --- originality: explain or rewrite (care-ful interaction) ---------------
def test_ask_to_explain_is_neutral_recommend():
    req = ask_to_explain_or_rewrite(submission_ref=uuid4(), action=ExplainOrRewriteAction.EXPLAIN)
    assert req.action is ExplainOrRewriteAction.EXPLAIN
    assert req.rung == "recommend"
    assert "no penalty" in req.prompt.lower()


def test_ask_to_rewrite_message():
    req = ask_to_explain_or_rewrite(submission_ref=uuid4(), action=ExplainOrRewriteAction.REWRITE)
    assert "rewrite" in req.prompt.lower()


# --- risk-based reminders ------------------------------------------------
def test_reminders_skip_submitted_and_low_risk_with_time():
    now = datetime.now(timezone.utc)
    due = now + timedelta(days=3)  # plenty of time
    learners = [
        LearnerReminderState(canonical_uuid=uuid4(), submitted=True, risk=0.9),  # skipped: submitted
        LearnerReminderState(canonical_uuid=uuid4(), submitted=False, risk=0.1),  # skipped: low risk + time
        LearnerReminderState(canonical_uuid=uuid4(), submitted=False, risk=0.8),  # reminded: high risk
    ]
    plan = plan_reminders(assignment_id=uuid4(), due_at=due, learners=learners, now=now)
    assert plan.skipped_submitted == 1
    assert plan.skipped_low_risk == 1
    assert len(plan.reminders) == 1
    # Every prepared reminder requires human approval — never auto-sent.
    assert all(r.requires_approval for r in plan.reminders)
    assert plan.rung == "prepare"


def test_reminders_urgency_rises_near_deadline():
    now = datetime.now(timezone.utc)
    learner = LearnerReminderState(canonical_uuid=uuid4(), submitted=False, risk=0.5)
    soon = plan_reminders(
        assignment_id=uuid4(), due_at=now + timedelta(hours=3), learners=[learner], now=now
    )
    assert soon.reminders[0].urgency is ReminderUrgency.HIGH


def test_reminders_ordered_high_first():
    now = datetime.now(timezone.utc)
    due = now + timedelta(hours=12)
    learners = [
        LearnerReminderState(canonical_uuid=uuid4(), submitted=False, risk=0.4),
        LearnerReminderState(canonical_uuid=uuid4(), submitted=False, risk=0.95),
    ]
    plan = plan_reminders(assignment_id=uuid4(), due_at=due, learners=learners, now=now)
    urgencies = [r.urgency for r in plan.reminders]
    # Highest-risk learner appears first.
    assert plan.reminders[0].risk == 0.95
    assert ReminderUrgency.HIGH in urgencies


def test_reminders_past_due_is_high_and_prepared_only():
    now = datetime.now(timezone.utc)
    due = now - timedelta(hours=5)  # overdue
    learner = LearnerReminderState(canonical_uuid=uuid4(), submitted=False, risk=0.2)
    plan = plan_reminders(assignment_id=uuid4(), due_at=due, learners=[learner], now=now)
    assert len(plan.reminders) == 1
    assert plan.reminders[0].urgency is ReminderUrgency.HIGH
    assert plan.requires_approval is True
