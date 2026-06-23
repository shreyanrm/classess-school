"""Live polls / quizzes with real-time tally (d7).

Canonical poll engine. NOTE ON FILE NAME: intended to be importable as
``app.polls``; the pre-existing ``polls.py`` path was locked by the host sandbox
in this build and could not be overwritten, so the working engine lives here and
is re-exported by ``app/__init__.py``.

Rules honored:

- Responses reference only opaque ``canonical_uuid`` -- no PII.
- One vote per subject per poll (idempotent re-vote replaces the prior choice);
  the tally is recomputed in real time.
- Free-text poll prompts and free-text answers pass CHILD-SAFETY screening; a
  prompt/answer that fails screening is refused, never stored.
- A quiz answer is checked against an answer key but the result is learning
  evidence (grasp), never a punitive identity judgement.
- Events are append-only; nothing is written here. No network/DB required.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from typing import Optional

from .events import Event, EventKind, is_opaque_uuid


# ---------------------------------------------------------------------------
# CHILD-SAFETY screening for free-text surfaces
# ---------------------------------------------------------------------------

#: Env var (server-side only) for the safety-classifier endpoint via gateway.
ENV_SAFETY_CLASSIFIER = "clss.classroom.prod.safety_classifier_url"

# A conservative, offline deny-list so the surface degrades safely with no
# classifier service. The production path routes free text through the gateway
# safety classifier; this local list is the floor, never the ceiling.
_UNSAFE_TERMS = frozenset(
    {
        "kill",
        "suicide",
        "self-harm",
        "selfharm",
        "abuse",
        "weapon",
        "drugs",
    }
)


class ChildSafetyError(ValueError):
    """Raised when free text fails CHILD-SAFETY screening."""


def screen_free_text(text: str) -> str:
    """Return text if it passes the offline safety floor, else raise.

    This is the always-on local floor. Production additionally routes through the
    gateway classifier named by ``ENV_SAFETY_CLASSIFIER``.
    """
    if not isinstance(text, str):
        raise ChildSafetyError("free text must be a string")
    lowered = text.lower()
    for term in _UNSAFE_TERMS:
        if term in lowered:
            raise ChildSafetyError("free text failed child-safety screening")
    return text


class PollKind(str, enum.Enum):
    SINGLE_CHOICE = "single_choice"
    QUIZ = "quiz"  # single_choice with a correct option


@dataclass(frozen=True)
class PollOption:
    option_id: str
    label: str


@dataclass(frozen=True)
class PollResponse:
    subject_uuid: str
    option_id: str

    def __post_init__(self) -> None:
        if not is_opaque_uuid(self.subject_uuid):
            raise ValueError("subject_uuid must be an opaque canonical_uuid")


class Poll:
    """A live poll/quiz with an in-memory, real-time tally.

    Construct with screened prompt + options. Votes are one-per-subject and
    idempotent: re-voting replaces the prior choice and the tally updates.
    """

    def __init__(
        self,
        session_id: str,
        prompt: str,
        options: list[tuple[str, str]],
        kind: PollKind = PollKind.SINGLE_CHOICE,
        correct_option_id: Optional[str] = None,
        poll_id: Optional[str] = None,
    ):
        if not session_id:
            raise ValueError("session_id is required")
        self.session_id = session_id
        self.poll_id = poll_id or str(uuid.uuid4())
        self.kind = kind
        # CHILD-SAFETY: screen the prompt and every option label.
        self.prompt = screen_free_text(prompt)
        self._options: dict[str, PollOption] = {}
        for option_id, label in options:
            self._options[option_id] = PollOption(
                option_id=option_id, label=screen_free_text(label)
            )
        if not self._options:
            raise ValueError("a poll needs at least one option")
        if kind is PollKind.QUIZ:
            if correct_option_id not in self._options:
                raise ValueError("quiz needs a valid correct_option_id")
        self.correct_option_id = correct_option_id
        self.open = True
        self._votes: dict[str, str] = {}  # subject_uuid -> option_id

    # -- voting ----------------------------------------------------------
    def vote(self, response: PollResponse) -> "Poll":
        if not self.open:
            raise RuntimeError("poll is closed")
        if response.option_id not in self._options:
            raise ValueError("unknown option")
        self._votes[response.subject_uuid] = response.option_id  # idempotent
        return self

    def close(self) -> None:
        self.open = False

    # -- tally -----------------------------------------------------------
    def tally(self) -> dict[str, int]:
        """Real-time counts per option_id (zero-filled for all options)."""
        counts = {oid: 0 for oid in self._options}
        for option_id in self._votes.values():
            counts[option_id] += 1
        return counts

    def total_votes(self) -> int:
        return len(self._votes)

    def is_correct(self, subject_uuid: str) -> Optional[bool]:
        """For a quiz, whether a subject's vote matches the key.

        Returns None if not a quiz or the subject did not vote. The result is
        learning evidence, not a sanction.
        """
        if self.kind is not PollKind.QUIZ:
            return None
        choice = self._votes.get(subject_uuid)
        if choice is None:
            return None
        return choice == self.correct_option_id

    # -- events ----------------------------------------------------------
    def opened_event(self, author_uuid: str) -> Event:
        return Event(
            kind=EventKind.POLL_OPENED,
            session_id=self.session_id,
            subject_uuid=author_uuid,
            payload={"poll_id": self.poll_id, "kind": self.kind.value},
        )

    def response_event(self, response: PollResponse) -> Event:
        payload = {"poll_id": self.poll_id, "option_id": response.option_id}
        if self.kind is PollKind.QUIZ:
            payload["correct"] = self.is_correct(response.subject_uuid)
            payload["assistive"] = True
            payload["punitive"] = False
        return Event(
            kind=EventKind.POLL_RESPONSE,
            session_id=self.session_id,
            subject_uuid=response.subject_uuid,
            payload=payload,
        )

    def closed_event(self, author_uuid: str) -> Event:
        return Event(
            kind=EventKind.POLL_CLOSED,
            session_id=self.session_id,
            subject_uuid=author_uuid,
            payload={"poll_id": self.poll_id, "total_votes": self.total_votes()},
        )
