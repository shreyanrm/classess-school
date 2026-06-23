"""Device-free room-photo quiz + live leaderboard (d7).

Where students do NOT have devices, an on-the-spot quiz still runs: each student
holds a unique multi-sided response card and the teacher photographs the room.
On-device vision reduces the photo to a set of (opaque card-code -> shown side)
detections; this module maps those detections to answers, tallies them against
the quiz key, and maintains a live leaderboard. Quizzes link to the day's lesson
so the teacher can quantify what was actually grasped.

Hard rules honored:

- The photo is processed ON-DEVICE into a reduced descriptor. This module never
  accepts a raw image / face; it accepts only ``CardDetection`` records (an
  opaque card code + the detected side + a per-detection confidence).
- Generate-and-verify: a detection below the confidence gate is held back as
  UNRESOLVED, never guessed into an answer.
- A card code resolves to an opaque ``canonical_uuid`` only -- no PII, no face.
- A wrong answer is LEARNING EVIDENCE (grasp), never a punitive identity verdict;
  the leaderboard ranks scores, never ranks people by name.
- Re-photographing the same checkpoint is idempotent per (subject, question):
  a clearer later detection updates the same answer rather than stacking.
- Emitting a capture is a gateway-routed event; nothing is written here. No
  network / DB; degrades to an in-memory tally.
"""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from .device_free_check import ScanCard, is_valid_scan_code
from .events import Event, EventKind, is_opaque_uuid

#: Confidence gate below which a card-side detection is UNRESOLVED, not an answer.
DETECTION_CONFIDENCE_GATE = 0.60


class CaptureOutcome(str, enum.Enum):
    RESOLVED = "resolved"  # detection mapped to an answer above the gate
    UNRESOLVED = "unresolved"  # below gate / unknown card -> held back
    UNKNOWN_CARD = "unknown_card"


@dataclass(frozen=True)
class CardDetection:
    """One on-device detection from the room photo (a reduced descriptor).

    ``side`` is the response-card side the student showed (e.g. an option id like
    "a"/"b"/"c"/"d"). This is NOT an image and NOT a face -- it is the output of
    on-device vision, carrying only the opaque card code, the detected side, and a
    confidence.
    """

    card_code: str
    side: str
    confidence: float

    def __post_init__(self) -> None:
        if not is_valid_scan_code(self.card_code):
            raise ValueError("card_code is malformed")
        if not self.side:
            raise ValueError("a detection must carry a detected side")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be in [0, 1]")

    @property
    def resolved(self) -> bool:
        return self.confidence >= DETECTION_CONFIDENCE_GATE


@dataclass(frozen=True)
class CaptureResult:
    """The outcome of mapping one detection to an answer."""

    question_id: str
    subject_uuid: Optional[str]
    side: Optional[str]
    outcome: CaptureOutcome
    correct: Optional[bool] = None
    captured_at: float = field(default_factory=time.time)

    @property
    def is_resolved(self) -> bool:
        return self.outcome is CaptureOutcome.RESOLVED


@dataclass(frozen=True)
class LeaderboardRow:
    """One leaderboard row: an opaque subject and their running score.

    The leaderboard ranks by score only; it carries no PII and never ranks a
    person by name. ``answered`` is how many questions the subject has resolved.
    """

    subject_uuid: str
    score: int
    answered: int


class RoomQuiz:
    """A device-free, room-photo quiz with a live leaderboard.

    Register one card per participant, set the answer key per question, then feed
    on-device card detections from each room photo. Resolved detections are scored
    against the key and the leaderboard updates in real time. Quiz is linked to a
    lesson via ``lesson_ref`` so grasp can be tied back to the day's topic.
    """

    def __init__(
        self,
        session_id: str,
        *,
        lesson_ref: Optional[str] = None,
        quiz_id: Optional[str] = None,
    ) -> None:
        if not session_id:
            raise ValueError("session_id is required")
        self.session_id = session_id
        self.quiz_id = quiz_id or str(uuid.uuid4())
        self.lesson_ref = lesson_ref
        self._cards: dict[str, ScanCard] = {}
        self._answer_key: dict[str, str] = {}  # question_id -> correct side
        # (question_id, subject_uuid) -> resolved side
        self._answers: dict[tuple[str, str], str] = {}

    # -- setup -----------------------------------------------------------
    def register_card(self, card: ScanCard) -> None:
        self._cards[card.code] = card

    def set_answer_key(self, question_id: str, correct_side: str) -> None:
        if not question_id or not correct_side:
            raise ValueError("question_id and correct_side are required")
        self._answer_key[question_id] = correct_side

    # -- capture ---------------------------------------------------------
    def capture(self, question_id: str, detection: CardDetection) -> CaptureResult:
        """Map one on-device detection to an answer for a question.

        Unknown cards and below-gate detections are held back (never guessed).
        Idempotent per (subject, question): a clearer later detection replaces an
        earlier one for the same subject + question.
        """
        if question_id not in self._answer_key:
            raise ValueError("unknown question_id (set the answer key first)")

        card = self._cards.get(detection.card_code)
        if card is None:
            return CaptureResult(
                question_id=question_id,
                subject_uuid=None,
                side=None,
                outcome=CaptureOutcome.UNKNOWN_CARD,
            )
        if not detection.resolved:
            return CaptureResult(
                question_id=question_id,
                subject_uuid=card.subject_uuid,
                side=None,
                outcome=CaptureOutcome.UNRESOLVED,
            )

        self._answers[(question_id, card.subject_uuid)] = detection.side
        correct = detection.side == self._answer_key[question_id]
        return CaptureResult(
            question_id=question_id,
            subject_uuid=card.subject_uuid,
            side=detection.side,
            outcome=CaptureOutcome.RESOLVED,
            correct=correct,
        )

    def capture_photo(
        self, question_id: str, detections: list[CardDetection]
    ) -> list[CaptureResult]:
        """Process every detection from one room photo for a question."""
        return [self.capture(question_id, d) for d in detections]

    # -- leaderboard -----------------------------------------------------
    def leaderboard(self) -> list[LeaderboardRow]:
        """Live leaderboard, descending by score then ascending by opaque uuid.

        Ranks scores only -- never ranks a person by name. Deterministic ordering
        so a tie is stable.
        """
        score: dict[str, int] = {}
        answered: dict[str, int] = {}
        for (question_id, subject_uuid), side in self._answers.items():
            answered[subject_uuid] = answered.get(subject_uuid, 0) + 1
            if side == self._answer_key.get(question_id):
                score[subject_uuid] = score.get(subject_uuid, 0) + 1
            else:
                score.setdefault(subject_uuid, 0)
        rows = [
            LeaderboardRow(
                subject_uuid=u,
                score=score.get(u, 0),
                answered=answered.get(u, 0),
            )
            for u in answered
        ]
        rows.sort(key=lambda r: (-r.score, r.subject_uuid))
        return rows

    def score_for(self, subject_uuid: str) -> int:
        if not is_opaque_uuid(subject_uuid):
            raise ValueError("subject_uuid must be an opaque canonical_uuid")
        return sum(
            1
            for (qid, u), side in self._answers.items()
            if u == subject_uuid and side == self._answer_key.get(qid)
        )

    # -- events ----------------------------------------------------------
    def capture_event(self, result: CaptureResult) -> Optional[Event]:
        """Build an append-only capture event for a resolved answer.

        Returns None for unresolved / unknown detections (nothing to record about
        a person). The event is learning evidence -- assistive, never punitive.
        """
        if not result.is_resolved or result.subject_uuid is None:
            return None
        payload = {
            "quiz_id": self.quiz_id,
            "question_id": result.question_id,
            "correct": result.correct,
            "assistive": True,
            "punitive": False,
        }
        if self.lesson_ref is not None:
            payload["lesson_ref"] = self.lesson_ref
        return Event(
            kind=EventKind.ROOM_PHOTO_CAPTURE,
            session_id=self.session_id,
            subject_uuid=result.subject_uuid,
            payload=payload,
        )
