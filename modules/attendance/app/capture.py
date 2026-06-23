"""Multi-method attendance capture (B8 / d8 "Fast, flexible capture").

Several capture methods, each of which ASSISTS the teacher: a classroom
photo-scan, voice roll-call, a photo roster, absent-only marking, and verified
online-class presence. Manual marking is always a first-class option.

THE NON-NEGOTIABLE RULE (d8): the assisting methods *propose*; the teacher
*confirms*. Attendance is NEVER finalised automatically. This is INVARIANT 3
(human authority) and the permission ladder (INVARIANT 8): capture sits at the
``prepare`` rung — it prepares a proposed roll, and only a human, by confirming,
moves it to finalised.

A capture method produces a :class:`DraftRoll`: a mutable, in-progress roll of
per-learner :class:`Mark` proposals. A draft is NEVER final
(``draft.is_final`` is always ``False``); the only path to a
:class:`FinalisedRoll` is :func:`confirm_roll`, which REQUIRES an opaque human
ref. The draft object is left untouched by confirmation (append-only / immutable
shape): confirmation returns a new finalised roll.

Each :class:`Mark` carries a confidence in [0,1]; a mark below
:data:`CONFIDENCE_GATE` is flagged ``needs_review`` and lands in the draft's
``review_queue`` for the teacher to look at before confirming. Reconciliation
(reconciliation.py) cross-checks marks from different method drafts.

OFFLINE-CAPABLE SHAPE (principle 8): a draft is a plain, in-memory structure
built and confirmed with no network and no provider, then synced later.

PII: marks and rolls carry ONLY opaque learner refs (``canonical_uuid``) — never
a name, photo, or biometric template. Photo / voice / face artefacts live in the
capture surface and never enter a mark or an event (INVARIANT 1 + 2). Free-text
notes are screened (safety.py) before they are ever attached.

Import-safe: no I/O, no provider, no secret value read at import.
"""

from __future__ import annotations

import uuid as _uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Iterable, List, Mapping, NamedTuple, Optional, Sequence

from .safety import screen_free_text


# Marks at or above this confidence are accepted without a review flag; below it
# the mark is surfaced for the teacher. A deliberate, documented prior — never a
# threshold that auto-decides attendance.
CONFIDENCE_GATE = 0.5


class Method(str, Enum):
    """The capture methods. Every one ASSISTS — none finalises."""

    PHOTO_SCAN = "photo_scan"            # classroom photo, faces proposed
    VOICE = "voice"                      # spoken roll-call, names proposed
    PHOTO_ROSTER = "photo_roster"        # tap faces on a roster grid
    ABSENT_ONLY = "absent_only"          # mark absentees; rest presumed present
    ONLINE_PRESENCE = "online_presence"  # verified online-class join/dwell
    MANUAL = "manual"                    # always-available first-class fallback


class Status(str, Enum):
    """The status a learner can hold in a roll."""

    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"          # late arrival / short online dwell
    EXCUSED = "excused"    # absence with an approved reason
    UNKNOWN = "unknown"    # no usable signal — must be resolved before confirm


# Statuses that count as "in attendance" for downstream rollups.
_PRESENT_LIKE = frozenset({Status.PRESENT, Status.LATE, Status.EXCUSED})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return prefix + "_" + _uuid.uuid4().hex


def _coerce_status(value: "Status | str") -> Status:
    if isinstance(value, Status):
        return value
    return Status(value)


class VoiceMark(NamedTuple):
    """One spoken roll-call response: an opaque learner ref, a status (string or
    :class:`Status`), and a recogniser confidence in [0,1]."""

    canonical_uuid: str
    status: "Status | str"
    confidence: float = 1.0


@dataclass(frozen=True)
class Mark:
    """One method's PROPOSAL for one learner. A mark is evidence, never a
    decision. Carries only an opaque ``canonical_uuid`` — never a name, photo,
    or biometric template.

    ``needs_review`` is set when the mark's confidence is below
    :data:`CONFIDENCE_GATE`, or when the method could not positively detect the
    learner (it is surfaced for the teacher rather than silently asserted).
    """

    canonical_uuid: str
    status: Status
    method: Method
    confidence: float = 1.0
    needs_review: bool = False
    note: str = ""

    def __post_init__(self) -> None:
        if not self.canonical_uuid:
            raise ValueError("Mark requires an opaque canonical_uuid.")
        if "@" in self.canonical_uuid:
            raise ValueError("canonical_uuid must be opaque, not PII.")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0,1].")


def _mark(
    canonical_uuid: str,
    status: Status,
    method: Method,
    confidence: float,
    *,
    needs_review: bool = False,
    note: str = "",
) -> Mark:
    """Build a mark, auto-flagging review when confidence is below the gate."""
    review = needs_review or confidence < CONFIDENCE_GATE
    return Mark(
        canonical_uuid=canonical_uuid,
        status=status,
        method=method,
        confidence=float(confidence),
        needs_review=review,
        note=note,
    )


@dataclass
class DraftRoll:
    """A proposed roll for one session. ASSISTS only — NEVER final.

    A draft is built by a capture method, reviewed by the teacher, and then
    confirmed (see :func:`confirm_roll`). ``is_final`` is always ``False`` on a
    draft; ``confirmed_by`` / ``confirmed_at`` are always ``None``. The single
    path to a finalised roll is an explicit, human-attributed confirm.
    """

    session_id: str
    method: Method
    marks: List[Mark] = field(default_factory=list)
    draft_id: str = field(default_factory=lambda: _new_id("draft"))
    created_at: str = field(default_factory=_now)

    # -- invariant accessors: a draft is never final -----------------------

    @property
    def status(self) -> str:
        return "draft"

    @property
    def is_final(self) -> bool:
        return False

    @property
    def confirmed_by(self) -> Optional[str]:
        return None

    @property
    def confirmed_at(self) -> Optional[str]:
        return None

    @property
    def review_queue(self) -> List[Mark]:
        """Marks the teacher should look at before confirming."""
        return [m for m in self.marks if m.needs_review]


@dataclass(frozen=True)
class FinalisedRoll:
    """An immutable, human-confirmed roll. Produced ONLY by
    :func:`confirm_roll`. Carries opaque learner refs only."""

    session_id: str
    method: Method
    marks: Sequence[Mark]
    confirmed_by: str
    confirmed_at: str
    note: str = ""
    draft_id: str = ""
    roll_id: str = field(default_factory=lambda: _new_id("roll"))

    @property
    def status(self) -> str:
        return "final"

    @property
    def is_final(self) -> bool:
        return True

    def absent_refs(self) -> List[str]:
        return [m.canonical_uuid for m in self.marks if m.status is Status.ABSENT]

    def present_refs(self) -> List[str]:
        return [m.canonical_uuid for m in self.marks if m.status in _PRESENT_LIKE]


# ---------------------------------------------------------------------------
# Capture methods — each builds a DRAFT of proposals; none finalises.
# ---------------------------------------------------------------------------


def _require_session(session_id: str) -> None:
    if not session_id:
        raise ValueError("session_id is required to capture a roll.")


def capture_photo_scan(
    session_id: str, detections: Mapping[str, str]
) -> DraftRoll:
    """Assist via a classroom photo-scan.

    ``detections`` maps an opaque learner ref to a short outcome string, e.g.
    ``"p"`` / ``"present"`` for a matched face, ``"absent"`` for one the scan
    could not place. The scan PROPOSES; a low-certainty placement is flagged for
    review. The provider is NOT called here (no network at this layer).
    """
    _require_session(session_id)
    marks: List[Mark] = []
    for ref, outcome in detections.items():
        o = (outcome or "").strip().lower()
        if o in ("absent", "a", "no"):
            status, conf = Status.ABSENT, 0.7
        elif o in ("p", "present", "yes", "y"):
            status, conf = Status.PRESENT, 0.7
        else:
            status, conf = Status.UNKNOWN, 0.3
        marks.append(_mark(ref, status, Method.PHOTO_SCAN, conf))
    return DraftRoll(session_id=session_id, method=Method.PHOTO_SCAN, marks=marks)


def capture_voice(session_id: str, responses: Iterable[VoiceMark]) -> DraftRoll:
    """Assist via a spoken roll-call.

    ``responses`` is a sequence of :class:`VoiceMark`. The recogniser confidence
    rides straight onto the mark; anything below :data:`CONFIDENCE_GATE` is
    surfaced for the teacher rather than silently trusted.
    """
    _require_session(session_id)
    marks = [
        _mark(
            r.canonical_uuid,
            _coerce_status(r.status),
            Method.VOICE,
            float(r.confidence),
        )
        for r in responses
    ]
    return DraftRoll(session_id=session_id, method=Method.VOICE, marks=marks)


def capture_photo_roster(
    session_id: str,
    roster_refs: Sequence[str],
    detected: Mapping[str, float],
) -> DraftRoll:
    """Assist via a photo-roster grid.

    ``detected`` maps the opaque refs the vision pass placed to a confidence in
    [0,1]; everyone PRESENT is proposed at that confidence. Every roster learner
    the pass did NOT detect is proposed ABSENT but flagged ``needs_review`` — an
    undetected face is the method's weakness, never proof of absence.
    """
    _require_session(session_id)
    marks: List[Mark] = []
    for ref in roster_refs:
        if ref in detected:
            marks.append(
                _mark(ref, Status.PRESENT, Method.PHOTO_ROSTER, float(detected[ref]))
            )
        else:
            marks.append(
                _mark(
                    ref,
                    Status.ABSENT,
                    Method.PHOTO_ROSTER,
                    0.6,
                    needs_review=True,
                    note="undetected",
                )
            )
    return DraftRoll(session_id=session_id, method=Method.PHOTO_ROSTER, marks=marks)


def capture_absent_only(
    session_id: str,
    roster_refs: Sequence[str],
    absent_refs: Iterable[str],
) -> DraftRoll:
    """Assist via absent-only marking: the teacher names only the absentees; the
    rest of the roster is PROPOSED present. Fast for a full classroom — still a
    proposal until the teacher confirms."""
    _require_session(session_id)
    absent = set(absent_refs)
    marks: List[Mark] = []
    for ref in roster_refs:
        status = Status.ABSENT if ref in absent else Status.PRESENT
        marks.append(_mark(ref, status, Method.ABSENT_ONLY, 0.95))
    return DraftRoll(session_id=session_id, method=Method.ABSENT_ONLY, marks=marks)


def capture_online_presence(
    session_id: str,
    roster_refs: Sequence[str],
    seconds_present: Mapping[str, float],
    threshold_seconds: float,
) -> DraftRoll:
    """Assist via verified online-class presence.

    ``seconds_present`` maps a learner ref to the seconds they were joined.
    ``>= threshold`` proposes PRESENT; a shorter join proposes LATE (joined but
    did not stay); no join at all proposes ABSENT. Presence in an online class is
    a signal, never proof of engagement, so this still only proposes.
    """
    _require_session(session_id)
    marks: List[Mark] = []
    for ref in roster_refs:
        if ref in seconds_present:
            secs = float(seconds_present[ref])
            if secs >= threshold_seconds:
                status, conf, note = Status.PRESENT, 0.85, "joined"
            else:
                status, conf, note = Status.LATE, 0.7, "short_join"
        else:
            status, conf, note = Status.ABSENT, 0.85, "no_join"
        marks.append(_mark(ref, status, Method.ONLINE_PRESENCE, conf, note=note))
    return DraftRoll(
        session_id=session_id, method=Method.ONLINE_PRESENCE, marks=marks
    )


def capture_manual(session_id: str, marks: Mapping[str, "Status | str"]) -> DraftRoll:
    """The always-available first-class manual method. ``marks`` maps an opaque
    ref to a status. Full confidence, but still a draft entry until the teacher
    confirms the whole roll."""
    _require_session(session_id)
    built = [
        _mark(ref, _coerce_status(status), Method.MANUAL, 1.0)
        for ref, status in marks.items()
    ]
    return DraftRoll(session_id=session_id, method=Method.MANUAL, marks=built)


# ---------------------------------------------------------------------------
# The human gate — confirmation turns a draft into an immutable roll.
# ---------------------------------------------------------------------------


def confirm_roll(
    roll: "DraftRoll | FinalisedRoll",
    *,
    confirmed_by: str,
    overrides: Optional[Mapping[str, "Status | str"]] = None,
    note: Optional[str] = None,
) -> FinalisedRoll:
    """The single path from a proposed draft to a finalised roll.

    Requires an opaque human ref (``confirmed_by``). The teacher MAY pass
    ``overrides`` (per-learner corrections) and a short ``note`` (screened for
    PII / child-safety before it is attached). There is deliberately no
    auto-confirm and no high-confidence shortcut: a consequential record is
    created only by an explicit human action (INVARIANT 3 + 8).

    The input draft is left UNCHANGED (append-only / immutable shape); a new
    :class:`FinalisedRoll` is returned. An already-final roll cannot be
    re-confirmed.
    """
    if isinstance(roll, FinalisedRoll) or getattr(roll, "is_final", False):
        raise ValueError("roll is already final; confirmed attendance is immutable.")
    if not confirmed_by or not confirmed_by.strip():
        raise ValueError(
            "confirm_roll requires an opaque human ref. Attendance is never "
            "finalised without a person confirming it."
        )

    screened_note = ""
    if note is not None:
        result = screen_free_text(note)
        if not result.ok:
            raise ValueError("note failed safety screen; route to human review.")
        screened_note = result.sanitized

    over = {ref: _coerce_status(s) for ref, s in (overrides or {}).items()}
    final_marks: List[Mark] = []
    seen: set[str] = set()
    for m in roll.marks:
        seen.add(m.canonical_uuid)
        if m.canonical_uuid in over:
            final_marks.append(
                replace(
                    m,
                    status=over[m.canonical_uuid],
                    confidence=1.0,
                    needs_review=False,
                    note="teacher_override",
                )
            )
        else:
            final_marks.append(m)
    # Overrides may also ADD a learner not in the draft.
    for ref, status in over.items():
        if ref not in seen:
            final_marks.append(
                _mark(ref, status, roll.method, 1.0, note="teacher_override")
            )

    return FinalisedRoll(
        session_id=roll.session_id,
        method=roll.method,
        marks=tuple(final_marks),
        confirmed_by=confirmed_by,
        confirmed_at=_now(),
        note=screened_note,
        draft_id=getattr(roll, "draft_id", ""),
    )


# ---------------------------------------------------------------------------
# Post-finalisation locked-correction with audit.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Correction:
    """An append-only correction to ONE learner's mark on a LOCKED roll.

    A finalised roll is immutable. When a genuine error must be fixed after
    finalisation, we never overwrite the original mark — we record a separate,
    append-only :class:`Correction` that supersedes it, carrying the full audit
    trail (who authorised it, when, why, and the before/after status). Reading
    a learner's effective status means applying the latest correction over the
    finalised mark.
    """

    session_id: str
    canonical_uuid: str
    previous_status: Status
    corrected_status: Status
    corrected_by: str          # opaque human ref — REQUIRED
    reason: str                # plain-language, PII-screened — REQUIRED
    corrected_at: str
    correction_id: str = field(default_factory=lambda: _new_id("corr"))


def correct_finalised_roll(
    roll: FinalisedRoll,
    canonical_uuid: str,
    corrected_status: "Status | str",
    *,
    corrected_by: str,
    reason: str,
) -> Correction:
    """Correct a single mark on an already-finalised (locked) roll.

    This is the ONLY sanctioned post-finalisation path. It does NOT mutate the
    roll (attendance, once finalised, is immutable): it returns a new,
    append-only :class:`Correction` that supersedes the mark for that learner.

    REQUIRES an opaque authorising human ref and a non-empty reason (the audit
    trail) — corrections to a locked record are consequential and never
    anonymous. The reason is PII / child-safety screened before it is attached.
    """

    if not isinstance(roll, FinalisedRoll) and not getattr(roll, "is_final", False):
        raise ValueError("only a finalised (locked) roll can be corrected.")
    if not canonical_uuid:
        raise ValueError("a learner ref is required to correct a mark.")
    if not corrected_by or not corrected_by.strip():
        raise ValueError(
            "correcting a locked record requires an opaque authorising human ref."
        )
    if not reason or not reason.strip():
        raise ValueError("a correction to a locked record requires a reason (audit).")

    screen = screen_free_text(reason)
    if not screen.ok:
        raise ValueError("correction reason failed safety screen; route to review.")

    new_status = _coerce_status(corrected_status)
    previous = next(
        (m.status for m in roll.marks if m.canonical_uuid == canonical_uuid),
        Status.UNKNOWN,
    )
    return Correction(
        session_id=roll.session_id,
        canonical_uuid=canonical_uuid,
        previous_status=previous,
        corrected_status=new_status,
        corrected_by=corrected_by,
        reason=screen.sanitized,
        corrected_at=_now(),
    )


def effective_status(
    roll: FinalisedRoll,
    canonical_uuid: str,
    corrections: Sequence[Correction] = (),
) -> Status:
    """The learner's effective status: the latest correction wins, else the
    finalised mark. The roll itself is never mutated."""

    relevant = [
        c
        for c in corrections
        if c.session_id == roll.session_id and c.canonical_uuid == canonical_uuid
    ]
    if relevant:
        relevant.sort(key=lambda c: c.corrected_at)
        return relevant[-1].corrected_status
    return next(
        (m.status for m in roll.marks if m.canonical_uuid == canonical_uuid),
        Status.UNKNOWN,
    )


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def summarize_draft(roll: "DraftRoll | FinalisedRoll") -> Dict[str, int]:
    """Plain-language counts for a draft or finalised roll, for an explainable
    surface. Counts every status plus how many marks still need review."""
    counts: Dict[str, int] = {s.value: 0 for s in Status}
    counts["needs_review"] = 0
    for m in roll.marks:
        counts[m.status.value] += 1
        if getattr(m, "needs_review", False):
            counts["needs_review"] += 1
    return counts
