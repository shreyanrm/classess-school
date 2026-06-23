"""Period launch (d7): assemble content + attendance + assessment for a session.

When a teacher launches a period from the timetable, the classroom is assembled
in one step: the board's subject-aware teaching content for the topic, the
attendance method for the room, and the in-class assessment (a poll/quiz or a
device-free room-photo quiz). This module is the deterministic ASSEMBLER -- it
gathers the pieces into a launch plan and emits a single launch event; it does
not open sockets, write a DB, or fire anything consequential on its own.

Rules honored:

- Behavioural references are opaque ``canonical_uuid`` only; the plan carries no
  PII (no roster names, no faces).
- Subject-aware content is GENERATE-AND-VERIFIED: only content that cleared the
  board's verify gate is attached to the launch; unverified content is reported
  as ``deferred`` and never shown.
- Launching the live session is CONSEQUENTIAL: the assembler PREPARES the plan
  and (when asked to start) returns a ``requires_approval`` marker -- it never
  auto-starts the session. The human teacher confirms the start.
- Free-text (the period title) passes CHILD-SAFETY screening.
- Degrades cleanly: with no attendance method or no assessment, the period still
  launches with whatever pieces are present.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from typing import Optional

from .board_state import BoardObject, ContentVerification
from .events import Event, EventKind, is_opaque_uuid
from .poll_engine import screen_free_text


class AttendanceMethod(str, enum.Enum):
    """How presence will be captured for this period (assistive; teacher confirms)."""

    PHOTO_SCAN = "photo_scan"
    VOICE_ROLL_CALL = "voice_roll_call"
    PHOTO_ROSTER = "photo_roster"
    ABSENT_ONLY = "absent_only"
    ONLINE_PRESENCE = "online_presence"
    MANUAL = "manual"


class AssessmentKind(str, enum.Enum):
    NONE = "none"
    LIVE_POLL = "live_poll"
    LIVE_QUIZ = "live_quiz"
    DEVICE_FREE_ROOM_QUIZ = "device_free_room_quiz"


@dataclass(frozen=True)
class ContentItem:
    """One piece of board content attached to the period.

    ``board_object`` is the typed content ref; ``verification`` is its
    per-session generate-and-verify metadata (None for plain ink/text/shape).
    """

    board_object: BoardObject
    verification: Optional[ContentVerification] = None

    @property
    def is_subject_aware(self) -> bool:
        return self.board_object.is_generated_content

    @property
    def shown_live(self) -> bool:
        """Subject-aware content is shown only when verified; other content always."""
        if not self.is_subject_aware:
            return True
        v = self.verification or self.board_object.verification
        return bool(v and v.verified)


@dataclass(frozen=True)
class LaunchPlan:
    """The assembled, ready-to-confirm plan for a period."""

    session_id: str
    topic: str
    title: str
    attendance_method: AttendanceMethod
    assessment_kind: AssessmentKind
    content_shown: tuple[ContentItem, ...]
    content_deferred: tuple[ContentItem, ...]
    teacher_uuid: str
    period_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @property
    def content_ready_count(self) -> int:
        return len(self.content_shown)

    @property
    def has_assessment(self) -> bool:
        return self.assessment_kind is not AssessmentKind.NONE


@dataclass(frozen=True)
class LaunchApproval:
    """A staged, consequential start. Never auto-fires.

    The assembler returns this from :meth:`PeriodLaunch.prepare_start`; a separate
    human approval (the teacher) is required to actually start the live session.
    """

    period_id: str
    session_id: str
    requested_by: str
    requires_approval: bool = True


@dataclass(frozen=True)
class TimetableEntry:
    """An opaque timetable slot the period is assembled FROM.

    Carries the topic to teach and the chosen room methods, plus opaque content
    refs the board content for the topic was generated under. No PII: the teacher
    is an opaque ``canonical_uuid`` and there is no roster here. This is the bridge
    the doc names ("period launch assembled from the timetable").
    """

    session_id: str
    topic: str
    teacher_uuid: str
    title: str = ""
    attendance_method: AttendanceMethod = AttendanceMethod.MANUAL
    assessment_kind: AssessmentKind = AssessmentKind.NONE

    def __post_init__(self) -> None:
        if not self.session_id:
            raise ValueError("session_id is required")
        if not self.topic:
            raise ValueError("a timetable entry must name its topic")
        if not is_opaque_uuid(self.teacher_uuid):
            raise ValueError("teacher_uuid must be an opaque canonical_uuid")


class PeriodLaunch:
    """Assembles a period: content + attendance + assessment, then prepares start.

    Construct with the session, topic and teacher; add content items (verified
    subject-aware content is shown, unverified is deferred), set the attendance
    method and assessment kind, then ``build`` the plan. Starting the live
    session is consequential and goes through ``prepare_start`` (requires human
    approval) -- this class never starts a session itself.
    """

    def __init__(
        self,
        session_id: str,
        topic: str,
        teacher_uuid: str,
        *,
        title: str = "",
    ) -> None:
        if not session_id:
            raise ValueError("session_id is required")
        if not topic:
            raise ValueError("a period must name its topic")
        if not is_opaque_uuid(teacher_uuid):
            raise ValueError("teacher_uuid must be an opaque canonical_uuid")
        self.session_id = session_id
        self.topic = topic
        self.teacher_uuid = teacher_uuid
        # CHILD-SAFETY: screen the free-text title.
        self.title = screen_free_text(title or topic)
        self._content: list[ContentItem] = []
        self._attendance = AttendanceMethod.MANUAL
        self._assessment = AssessmentKind.NONE
        self.period_id = str(uuid.uuid4())

    # -- timetable bridge ------------------------------------------------
    @classmethod
    def from_timetable_entry(
        cls, entry: "TimetableEntry", content: Optional[list[ContentItem]] = None
    ) -> "PeriodLaunch":
        """Assemble a period directly from a timetable slot.

        Carries the slot's topic, title, and pre-chosen attendance + assessment
        methods, plus any board content generated for the topic. Nothing
        consequential happens; call :meth:`build` then :meth:`prepare_start`.
        """
        launch = cls(
            entry.session_id,
            entry.topic,
            entry.teacher_uuid,
            title=entry.title,
        )
        launch.set_attendance(entry.attendance_method)
        launch.set_assessment(entry.assessment_kind)
        for item in content or []:
            launch.add_content(item)
        return launch

    # -- assembly --------------------------------------------------------
    def add_content(self, item: ContentItem) -> "PeriodLaunch":
        self._content.append(item)
        return self

    def set_attendance(self, method: AttendanceMethod) -> "PeriodLaunch":
        self._attendance = method
        return self

    def set_assessment(self, kind: AssessmentKind) -> "PeriodLaunch":
        self._assessment = kind
        return self

    def build(self) -> LaunchPlan:
        """Assemble the launch plan. Splits content into shown vs. deferred by the
        generate-and-verify gate; nothing consequential happens here."""
        shown = tuple(c for c in self._content if c.shown_live)
        deferred = tuple(c for c in self._content if not c.shown_live)
        return LaunchPlan(
            session_id=self.session_id,
            topic=self.topic,
            title=self.title,
            attendance_method=self._attendance,
            assessment_kind=self._assessment,
            content_shown=shown,
            content_deferred=deferred,
            teacher_uuid=self.teacher_uuid,
            period_id=self.period_id,
        )

    # -- consequential start (permission ladder) -------------------------
    def prepare_start(self, plan: LaunchPlan) -> LaunchApproval:
        """Stage the period start. Consequential -> requires human approval.

        Returns an approval marker with ``requires_approval`` True; it does NOT
        start the live session. The teacher must explicitly approve the start.
        """
        return LaunchApproval(
            period_id=plan.period_id,
            session_id=plan.session_id,
            requested_by=self.teacher_uuid,
        )

    def launched_event(self, plan: LaunchPlan) -> Event:
        """Build an append-only period-launched event describing the assembly.

        The event records what was assembled (counts + chosen methods), carrying
        no PII -- only the opaque teacher uuid as subject.
        """
        return Event(
            kind=EventKind.PERIOD_LAUNCHED,
            session_id=plan.session_id,
            subject_uuid=plan.teacher_uuid,
            payload={
                "period_id": plan.period_id,
                "topic": plan.topic,
                "attendance_method": plan.attendance_method.value,
                "assessment_kind": plan.assessment_kind.value,
                "content_shown": plan.content_ready_count,
                "content_deferred": len(plan.content_deferred),
            },
        )
