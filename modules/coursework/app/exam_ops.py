"""Exam operations — secure delivery, scheduling, seating, scan + proctoring (B6, domain 10).

The dossier: "Online, offline, and hybrid exams ... secure printing, scanning,
scheduling, seating, and online proctoring ... proctoring watches for
irregularities while accommodations and accessibility settings are first-class."

This module is the OPERATIONS layer around an exam: it does NOT author or grade.
It schedules sittings, allocates seating under constraints, packages a paper for
SECURE PRINT, defines the OMR/scan INTAKE interface, and defines the PROCTORING
SIGNAL interface. The hard rules baked in:

  - HUMAN-FINAL on everything consequential (permission ladder). Scheduling,
    seating, the secure-print release, and any action on a proctoring/scan signal
    all sit at RECOMMEND/PREPARE — a human invigilator/exam officer confirms.
    Nothing auto-fires.
  - NEVER PENALISE SCAN QUALITY. An OMR/scan intake NEVER converts a poor scan
    into a wrong/zero mark. A low-quality or ambiguous scan sets
    ``needs_human_review`` and is routed to a human — exactly the
    never-penalize-handwriting rule from ``contracts``, extended to scan intake.
  - A PROCTORING signal is a SIGNAL, never a verdict. It flags an irregularity
    for a human; it never auto-disqualifies, auto-fails, or accuses.
  - Behavioural data carries ONLY the opaque ``canonical_uuid`` — never PII.
    Candidates, invigilators, and rooms are opaque refs.
  - ACCOMMODATIONS are first-class: a candidate may carry accommodation flags
    (extra time, separate room, scribe, large print) that the schedule and
    seating honour rather than treat as exceptions.

Degrades gracefully: no OCR provider and no proctoring provider are required.
With none configured, the intake/proctoring interfaces return clean, clearly
labelled DEGRADED results that route everything to a human — they never fabricate
a confident read. The provider key NAMES are ``clss.coursework.dev.ocr_provider_key``
and a (new) proctoring key, read by NAME, never hardcoded.

Pure: no I/O, no network, no provider call. Import-safe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Protocol
from uuid import UUID, uuid4


# ---------------------------------------------------------------------------
# Accommodations — first-class, honoured by schedule + seating.
# ---------------------------------------------------------------------------
class Accommodation(str, Enum):
    """First-class accessibility accommodations. Honoured, never an afterthought."""

    EXTRA_TIME = "extra_time"
    SEPARATE_ROOM = "separate_room"
    SCRIBE = "scribe"
    LARGE_PRINT = "large_print"
    ASSISTIVE_TECH = "assistive_tech"


@dataclass(frozen=True)
class Candidate:
    """An exam candidate — an opaque ref plus accommodation flags. No PII."""

    canonical_uuid: UUID
    accommodations: frozenset[Accommodation] = frozenset()

    @property
    def needs_separate_room(self) -> bool:
        return Accommodation.SEPARATE_ROOM in self.accommodations or Accommodation.SCRIBE in self.accommodations

    @property
    def extra_time_factor(self) -> float:
        """Extra-time multiplier on the base duration (a common 1.25x). 1.0 when
        no extra-time accommodation applies."""
        return 1.25 if Accommodation.EXTRA_TIME in self.accommodations else 1.0


@dataclass(frozen=True)
class Room:
    """An exam room — opaque ref, capacity, and a seat grid (rows x cols)."""

    room_id: UUID
    rows: int
    cols: int
    label: str = ""

    def __post_init__(self) -> None:
        if self.rows < 1 or self.cols < 1:
            raise ValueError("a room needs at least one row and one column.")

    @property
    def capacity(self) -> int:
        return self.rows * self.cols


# ---------------------------------------------------------------------------
# Scheduling — RECOMMEND rung; a human exam officer confirms.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ScheduledSitting:
    """A proposed exam sitting. A RECOMMENDATION an exam officer confirms — never
    auto-published. ``duration`` already folds in the longest extra-time the
    candidate set requires when ``honour_extra_time`` is set."""

    exam_id: UUID
    starts_at: datetime
    duration: timedelta
    candidate_count: int
    honoured_extra_time: bool
    rationale: str
    sitting_id: UUID = field(default_factory=uuid4)

    @property
    def rung(self) -> str:
        return "recommend"

    @property
    def ends_at(self) -> datetime:
        return self.starts_at + self.duration


class SchedulingError(ValueError):
    """A scheduling constraint was violated (e.g. a sitting in the past)."""


def schedule_sitting(
    *,
    exam_id: UUID,
    starts_at: datetime,
    base_duration: timedelta,
    candidates: list[Candidate],
    honour_extra_time: bool = True,
    now: datetime | None = None,
) -> ScheduledSitting:
    """Propose a sitting at ``starts_at`` for ``candidates``.

    Constraints checked: the start must be in the future, and the base duration
    must be positive. When ``honour_extra_time`` is set, the sitting duration is
    extended to the LONGEST extra-time any candidate requires, so the whole room
    runs to a single, accommodation-honouring schedule. Returns a RECOMMENDATION;
    an exam officer confirms before it is published.
    """
    now = now or datetime.now(timezone.utc)
    if starts_at <= now:
        raise SchedulingError("a sitting must be scheduled in the future.")
    if base_duration <= timedelta(0):
        raise SchedulingError("base_duration must be positive.")

    factor = 1.0
    if honour_extra_time and candidates:
        factor = max(c.extra_time_factor for c in candidates)
    duration = timedelta(seconds=base_duration.total_seconds() * factor)
    honoured = factor > 1.0

    rationale = (
        f"Proposed sitting for {len(candidates)} candidate(s) at {starts_at.isoformat()}. "
        + (
            f"Duration extended x{factor:g} to honour extra-time accommodations."
            if honoured
            else "Standard duration; no extra-time accommodation in this cohort."
        )
        + " Recommendation for an exam officer to confirm before publishing."
    )
    return ScheduledSitting(
        exam_id=exam_id,
        starts_at=starts_at,
        duration=duration,
        candidate_count=len(candidates),
        honoured_extra_time=honoured,
        rationale=rationale,
    )


# ---------------------------------------------------------------------------
# Seating allocation — constraint-aware; RECOMMEND rung.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SeatAssignment:
    """One candidate placed at a seat. ``row``/``col`` are 0-indexed."""

    candidate: UUID
    room_id: UUID
    row: int
    col: int


@dataclass(frozen=True)
class SeatingPlan:
    """A proposed seating plan across rooms. A RECOMMENDATION an invigilator
    confirms. Candidates that could not be placed are surfaced, never dropped."""

    seats: list[SeatAssignment]
    unplaced: list[UUID]
    rationale: str

    @property
    def rung(self) -> str:
        return "recommend"

    @property
    def fully_seated(self) -> bool:
        return not self.unplaced


class SeatingError(ValueError):
    """Seating constraints cannot be satisfied (e.g. not enough capacity)."""


def allocate_seating(
    *,
    candidates: list[Candidate],
    rooms: list[Room],
    spacing: int = 1,
) -> SeatingPlan:
    """Allocate seats under anti-malpractice + accommodation constraints.

    Constraints:
      - ``spacing`` enforces a minimum gap between occupied seats in a row
        (spacing=1 leaves an empty seat between candidates) to reduce the
        malpractice surface.
      - candidates needing a SEPARATE_ROOM (separate-room or scribe accommodation)
        are placed in a room on their own where capacity allows, never beside
        another candidate.
      - capacity is checked; if it cannot fit everyone under the constraints, the
        overflow is returned as ``unplaced`` (never silently seated double).

    Returns a RECOMMENDATION; an invigilator confirms.
    """
    if spacing < 0:
        raise SeatingError("spacing must be >= 0.")
    if not rooms:
        raise SeatingError("at least one room is required to seat candidates.")

    seats: list[SeatAssignment] = []
    unplaced: list[UUID] = []

    separate = [c for c in candidates if c.needs_separate_room]
    general = [c for c in candidates if not c.needs_separate_room]

    # A mutable cursor per room walking the spaced grid.
    room_cursors: dict[UUID, list[tuple[int, int]]] = {
        r.room_id: _spaced_seats(r, spacing) for r in rooms
    }
    room_by_id = {r.room_id: r for r in rooms}

    # Separate-room candidates first: give each its own room if one is free.
    used_rooms: set[UUID] = set()
    for cand in separate:
        placed = False
        for r in rooms:
            if r.room_id in used_rooms:
                continue
            grid = room_cursors[r.room_id]
            if grid:
                row, col = grid.pop(0)
                seats.append(SeatAssignment(candidate=cand.canonical_uuid, room_id=r.room_id, row=row, col=col))
                used_rooms.add(r.room_id)  # reserve the room solely for this candidate
                room_cursors[r.room_id] = []  # consume the rest of this room
                placed = True
                break
        if not placed:
            unplaced.append(cand.canonical_uuid)

    # General candidates: fill remaining spaced seats across the open rooms.
    open_rooms = [r for r in rooms if r.room_id not in used_rooms]
    for cand in general:
        placed = False
        for r in open_rooms:
            grid = room_cursors[r.room_id]
            if grid:
                row, col = grid.pop(0)
                seats.append(SeatAssignment(candidate=cand.canonical_uuid, room_id=r.room_id, row=row, col=col))
                placed = True
                break
        if not placed:
            unplaced.append(cand.canonical_uuid)

    total_spaced = sum(len(_spaced_seats(room_by_id[r.room_id], spacing)) for r in rooms)
    if unplaced:
        rationale = (
            f"Seated {len(seats)} candidate(s); {len(unplaced)} could not be placed under "
            f"spacing={spacing} and accommodation constraints (spaced capacity {total_spaced}). "
            "Add rooms or reduce spacing. Recommendation for an invigilator to confirm or adjust."
        )
    else:
        rationale = (
            f"Seated all {len(seats)} candidate(s) with spacing={spacing}; "
            f"{len(separate)} placed in a separate room for accommodations. "
            "Recommendation for an invigilator to confirm."
        )

    return SeatingPlan(seats=seats, unplaced=unplaced, rationale=rationale)


def _spaced_seats(room: Room, spacing: int) -> list[tuple[int, int]]:
    """The (row, col) seats of a room honouring a minimum column gap ``spacing``.
    spacing=0 uses every seat; spacing=1 leaves a gap between occupants."""
    step = spacing + 1
    return [(r, c) for r in range(room.rows) for c in range(0, room.cols, step)]


# ---------------------------------------------------------------------------
# Secure-print packaging — PREPARE rung; release needs human approval.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SecurePrintPackage:
    """A paper packaged for secure print. PREPARED, not released: the package is
    sealed (a content hash, a watermark token, a serial) but its RELEASE to a
    print queue is a consequential action requiring explicit human approval. The
    package carries NO secret value and NO PII — only opaque refs and a hash."""

    package_id: UUID
    exam_id: UUID
    set_label: str
    item_count: int
    content_hash: str
    watermark_token: str
    serial: str
    released: bool = False
    released_by: UUID | None = None

    @property
    def rung(self) -> str:
        """PREPARE — the package is ready; releasing it is the human-approved step."""
        return "prepare"


def package_for_secure_print(
    *,
    exam_id: UUID,
    set_label: str,
    item_prompts: list[str],
    serial: str,
) -> SecurePrintPackage:
    """Package a paper's items for secure print (PREPARE rung).

    Produces a sealed package: a content hash over the items (integrity, tamper
    evidence), a per-package watermark token, and a serial for chain-of-custody.
    It does NOT release the package — release is a separate human-approved action
    (``release_secure_print``). No secret value or PII is embedded.
    """
    import hashlib

    digest = hashlib.sha256("␟".join(item_prompts).encode("utf-8")).hexdigest()
    watermark = uuid4().hex[:12]
    return SecurePrintPackage(
        package_id=uuid4(),
        exam_id=exam_id,
        set_label=set_label,
        item_count=len(item_prompts),
        content_hash=digest,
        watermark_token=watermark,
        serial=serial,
    )


def release_secure_print(package: SecurePrintPackage, *, approved_by: UUID) -> SecurePrintPackage:
    """Release a prepared package to print — the EXECUTE-WITH-PERMISSION step.

    Requires an explicit ``approved_by`` (a human exam officer). Returns a new,
    released package; the original is never mutated in place (the prepared record
    stands as audit evidence). The permission ladder is enforced structurally:
    there is no path to a released package without ``approved_by``.
    """
    if approved_by is None:  # defensive; signature already requires it
        raise PermissionError("releasing a secure-print package requires explicit human approval.")
    return SecurePrintPackage(
        package_id=package.package_id,
        exam_id=package.exam_id,
        set_label=package.set_label,
        item_count=package.item_count,
        content_hash=package.content_hash,
        watermark_token=package.watermark_token,
        serial=package.serial,
        released=True,
        released_by=approved_by,
    )


# ---------------------------------------------------------------------------
# OMR / scan intake — NEVER penalises scan quality.
# ---------------------------------------------------------------------------
class ScanQuality(str, Enum):
    """How readable a scanned sheet is. NEVER affects a mark — only routing."""

    CLEAR = "clear"
    DEGRADED = "degraded"
    UNREADABLE = "unreadable"


@dataclass(frozen=True)
class OMRBubble:
    """One OMR response read from a scan: the chosen option (if any) and the
    intake's confidence in that read, in [0,1]."""

    question_index: int
    chosen_option: str | None
    read_confidence: float


@dataclass(frozen=True)
class ScanIntakeResult:
    """The result of scanning one answer sheet. The cardinal rule: a poor or
    ambiguous scan NEVER becomes a wrong/zero mark — it sets
    ``needs_human_review`` and routes to a human. ``never_penalize_scan`` is a
    literal True carried on the wire so the rule travels with the result."""

    submission_ref: UUID
    quality: ScanQuality
    bubbles: list[OMRBubble]
    needs_human_review: bool
    never_penalize_scan: bool
    provider: str
    rationale: str

    @property
    def rung(self) -> str:
        return "recommend"


class OMRProvider(Protocol):
    """An external OMR/scan service. Returns the bubble reads + a quality read.

    With no provider configured, ``intake_scan`` returns a DEGRADED result that
    routes the whole sheet to a human — it never fabricates confident reads.
    """

    def read(self, *, image_ref: str) -> tuple[ScanQuality, list[OMRBubble]]:
        ...


# A per-bubble read at/below this confidence routes the SHEET to a human. A
# routing threshold, never a penalty threshold.
SCAN_REVIEW_CONFIDENCE = 0.6


def intake_scan(
    *,
    submission_ref: UUID,
    image_ref: str,
    provider: OMRProvider | None = None,
    review_confidence: float = SCAN_REVIEW_CONFIDENCE,
) -> ScanIntakeResult:
    """Intake one scanned answer sheet.

    With a ``provider``, its reads are used; with none, the result is DEGRADED and
    routed to a human (no provider, no fabricated read). A sheet is routed to a
    human when quality is not CLEAR, or any bubble read is at/below
    ``review_confidence`` — and in EVERY case the scan quality NEVER reduces a
    mark (``never_penalize_scan`` is always True). The actual marking is the
    evaluation engine's job, not this intake.
    """
    if provider is None:
        return ScanIntakeResult(
            submission_ref=submission_ref,
            quality=ScanQuality.UNREADABLE,
            bubbles=[],
            needs_human_review=True,
            never_penalize_scan=True,
            provider="no-OMR-provider (degraded — set clss.coursework.dev.ocr_provider_key)",
            rationale=(
                "No OMR provider configured — the sheet could not be read automatically and "
                "is routed to a human for manual entry. Scan quality never affects the mark."
            ),
        )

    quality, bubbles = provider.read(image_ref=image_ref)
    low_conf = any(b.read_confidence <= review_confidence for b in bubbles)
    needs_review = quality is not ScanQuality.CLEAR or low_conf

    if needs_review:
        rationale = (
            f"Scan quality '{quality.value}'"
            + ("; one or more bubble reads below the confidence threshold" if low_conf else "")
            + ". Routed to a human to confirm — scan quality never reduces the mark."
        )
    else:
        rationale = "Scan read cleanly; reads are high-confidence. The mark still comes from the evaluation engine."

    return ScanIntakeResult(
        submission_ref=submission_ref,
        quality=quality,
        bubbles=bubbles,
        needs_human_review=needs_review,
        never_penalize_scan=True,
        provider="external OMR provider",
        rationale=rationale,
    )


# ---------------------------------------------------------------------------
# Proctoring signal — a SIGNAL to a human, never a verdict.
# ---------------------------------------------------------------------------
class ProctoringEventKind(str, Enum):
    """Kinds of irregularity a proctoring service may surface. Each is a SIGNAL."""

    FACE_NOT_VISIBLE = "face_not_visible"
    MULTIPLE_FACES = "multiple_faces"
    FOCUS_LOST = "focus_lost"
    AUDIO_ANOMALY = "audio_anomaly"
    DEVICE_SWITCH = "device_switch"


@dataclass(frozen=True)
class ProctoringSignal:
    """One proctoring observation. A SIGNAL for a human to review — never a
    verdict, never an automatic disqualification. Severity informs the human; it
    never auto-acts."""

    candidate: UUID
    kind: ProctoringEventKind
    confidence: float
    at_offset_ms: int
    rationale: str

    @property
    def rung(self) -> str:
        """Always RECOMMEND — a proctoring signal is reviewed by a human; the
        system never auto-fails or auto-accuses a candidate."""
        return "recommend"


@dataclass(frozen=True)
class ProctoringReport:
    """The collected proctoring signals for one sitting. Carries the explicit,
    structural reminder that NO action is automatic: ``auto_action_taken`` is a
    literal False, and the report is a recommendation for a human invigilator."""

    sitting_id: UUID
    signals: list[ProctoringSignal]
    provider: str
    auto_action_taken: bool
    rationale: str

    @property
    def rung(self) -> str:
        return "recommend"

    @property
    def flagged(self) -> bool:
        return bool(self.signals)


class ProctoringProvider(Protocol):
    """An external proctoring service. Returns raw observed signals.

    With no provider, ``collect_proctoring`` returns an empty, clearly-labelled
    DEGRADED report — it never invents irregularities.
    """

    def observe(self, *, sitting_id: UUID) -> list[ProctoringSignal]:
        ...


def collect_proctoring(
    *,
    sitting_id: UUID,
    provider: ProctoringProvider | None = None,
) -> ProctoringReport:
    """Collect proctoring signals for a sitting.

    With a ``provider``, its observed signals are surfaced for human review; with
    none, an empty DEGRADED report is returned. In BOTH cases no action is taken
    automatically — ``auto_action_taken`` is always False. Acting on a signal
    (disqualify, void, escalate) is a consequential, human-approved decision that
    lives outside this module.
    """
    if provider is None:
        return ProctoringReport(
            sitting_id=sitting_id,
            signals=[],
            provider="no-proctoring-provider (degraded — set clss.coursework.dev.proctoring_provider_key)",
            auto_action_taken=False,
            rationale=(
                "No proctoring provider configured — no signals collected. "
                "Proctoring never auto-acts; any decision is a human's."
            ),
        )

    signals = provider.observe(sitting_id=sitting_id)
    rationale = (
        f"{len(signals)} proctoring signal(s) surfaced for human review. "
        "Each is a signal, not a verdict — the system takes no automatic action."
    )
    return ProctoringReport(
        sitting_id=sitting_id,
        signals=signals,
        provider="external proctoring provider",
        auto_action_taken=False,
        rationale=rationale,
    )
