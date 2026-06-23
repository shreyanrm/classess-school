"""\"What do I need to do today\": role-shaped synthesis from timetable + tasks +
permissions + progress — permission-aware, approval-aware, explainable."""

from __future__ import annotations

from app.companion import CompanionRole
from app.today import (
    Attention,
    Permissions,
    ProgressItem,
    TaskItem,
    TimetableItem,
    TodayItemKind,
    TodaySynthesizer,
)


def _syn() -> TodaySynthesizer:
    return TodaySynthesizer()


def test_consequential_action_is_surfaced_as_needs_approval_never_done():
    view = _syn().synthesise(
        role=CompanionRole.TEACHER,
        tasks=[TaskItem(title="Term reports", due="today", action="publish")],
        permissions=Permissions(can=frozenset({"publish"})),
    )
    approvals = view.approvals
    assert len(approvals) == 1
    assert approvals[0].requires_approval is True
    assert approvals[0].kind is TodayItemKind.APPROVAL
    assert approvals[0].attention is Attention.NEEDS_APPROVAL


def test_an_action_without_permission_is_withheld_not_shown_actionable():
    view = _syn().synthesise(
        role=CompanionRole.TEACHER,
        tasks=[TaskItem(title="Publish results", due="today", action="publish")],
        permissions=Permissions(can=frozenset()),  # no publish permission.
    )
    assert view.items == ()  # nothing actionable shown.
    assert any("permission to publish" in note for note in view.withheld_for_permission)


def test_today_is_ranked_by_attention_with_approvals_first():
    view = _syn().synthesise(
        role=CompanionRole.TEACHER,
        timetable=[TimetableItem(label="Maths", at="09:00")],
        tasks=[
            TaskItem(title="Mark homework", due="overdue", action="review", overdue=True),
            TaskItem(title="Send newsletter", due="today", action="send"),
        ],
        permissions=Permissions(can=frozenset({"review", "send"})),
        progress=[ProgressItem(label="Class 7B slipping", needs_attention=True, why="three missed checks")],
    )
    attentions = [i.attention for i in view.items]
    assert attentions == sorted(attentions, reverse=True)
    assert view.items[0].requires_approval is True  # the send approval is first.


def test_progress_only_surfaces_what_needs_attention():
    view = _syn().synthesise(
        role=CompanionRole.STUDENT,
        progress=[
            ProgressItem(label="all good", needs_attention=False, why="x"),
            ProgressItem(label="algebra check tomorrow", needs_attention=True, why="due soon"),
        ],
    )
    labels = [i.headline for i in view.items]
    assert "algebra check tomorrow" in labels
    assert "all good" not in labels


def test_every_item_carries_a_why():
    view = _syn().synthesise(
        role=CompanionRole.ADMIN,
        tasks=[TaskItem(title="Budget approval", due="today", action="approve")],
        permissions=Permissions(can=frozenset({"approve"})),
    )
    assert view.items
    for item in view.items:
        assert item.why  # explainable.


def test_role_shapes_the_greeting():
    syn = _syn()
    assert syn.greeting(CompanionRole.TEACHER) != syn.greeting(CompanionRole.PARENT)
