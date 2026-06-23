"""Live polls & quizzes with real-time tally (D7).

A teacher launches a poll or quiz mid-lesson and sees grasp immediately. This
module is the deterministic tally engine:

  - Poll: opinion/temperature check — options, no "correct" answer, live counts.
  - Quiz: graded-for-grasp — options with a correct key, live correctness tally,
    and a leaderboard. The quiz links to the day's lesson via an opaque ontology
    ref so the teacher can quantify what was actually grasped on that topic.

Anti-abuse / fairness:
  - One response per participant per question; a re-vote replaces the prior one
    (last-write-wins) while a poll/quiz is OPEN — never double-counts.
  - Responses lock once the question CLOSES; late responses are rejected.

PII discipline: a respondent is an opaque ``participant_ref`` (canonical UUID).
The leaderboard is by opaque ref; surfacing a display name is the role surface's
job, gated by consent — never this engine's.

CHILD-SAFETY: free-text is NOT a response channel here (poll/quiz answers are
option selections or short numeric/text quiz answers checked against a key). Any
free-text surface (e.g. an open-ended question prompt authored by a teacher) must
pass the child-safety filter at the authoring surface before it reaches here;
``assert_safe_prompt`` is provided as the seam and refuses on the deny-list.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable
from uuid import UUID, uuid4


# ---------------------------------------------------------------------------
# Child-safety seam for any free-text prompt that reaches this engine.
# ---------------------------------------------------------------------------
# A minimal, conservative deny-list. The real filter is the ai-fabric child-safety
# service behind the gateway; this is the import-safe local floor so a prompt is
# NEVER served unchecked when no provider is wired.
_UNSAFE_TOKENS = (
    "kill yourself",
    "self-harm",
    "suicide",
    "porn",
    "nude",
    "weapon to school",
)


def assert_safe_prompt(text: str) -> str:
    """Refuse an unsafe free-text prompt. Returns the text when it passes.

    This is the conservative local floor; production routes the same text through
    the child-safety service behind the gateway. It refuses rather than sanitises
    — a flagged prompt never reaches learners."""
    lowered = text.lower()
    for token in _UNSAFE_TOKENS:
        if token in lowered:
            raise ValueError("prompt refused by child-safety check")
    return text


# ---------------------------------------------------------------------------
# Poll / quiz definitions.
# ---------------------------------------------------------------------------
class QuestionKind(str, Enum):
    POLL = "poll"   # no correct answer
    QUIZ = "quiz"   # has a correct key


class QuestionStatus(str, Enum):
    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"


@dataclass(frozen=True)
class Option:
    option_id: UUID
    label: str


@dataclass(frozen=True)
class OntologyRef:
    """Opaque link to the day's lesson topic/outcome — never PII."""

    topic_id: UUID
    outcome_id: UUID | None = None


@dataclass
class LiveQuestion:
    """A poll or quiz question. The tally is computed live from responses."""

    question_id: UUID
    kind: QuestionKind
    prompt: str
    options: tuple[Option, ...]
    status: QuestionStatus = QuestionStatus.DRAFT
    correct_option_id: UUID | None = None  # required for QUIZ
    ontology: OntologyRef | None = None    # links a quiz to the lesson
    _responses: dict[UUID, UUID] = field(default_factory=dict)  # participant_ref -> option_id

    def __post_init__(self) -> None:
        assert_safe_prompt(self.prompt)
        if self.kind is QuestionKind.QUIZ and self.correct_option_id is None:
            raise ValueError("a quiz question requires correct_option_id")
        if self.correct_option_id is not None:
            valid = {o.option_id for o in self.options}
            if self.correct_option_id not in valid:
                raise ValueError("correct_option_id must be one of the options")

    # -- lifecycle ---------------------------------------------------------
    def open(self) -> None:
        if self.status is QuestionStatus.CLOSED:
            raise ValueError("a closed question cannot reopen")
        self.status = QuestionStatus.OPEN

    def close(self) -> None:
        self.status = QuestionStatus.CLOSED

    # -- responses ---------------------------------------------------------
    def respond(self, participant_ref: UUID, option_id: UUID) -> None:
        """Record/replace a participant's response. One per participant; rejected
        unless the question is OPEN."""
        if self.status is not QuestionStatus.OPEN:
            raise ValueError("question is not open for responses")
        valid = {o.option_id for o in self.options}
        if option_id not in valid:
            raise ValueError("unknown option")
        self._responses[participant_ref] = option_id  # last-write-wins, no double count

    @property
    def response_count(self) -> int:
        return len(self._responses)

    # -- tally -------------------------------------------------------------
    def tally(self) -> dict[UUID, int]:
        """Live per-option counts. Every option appears, including zero-count
        options, so the surface renders a stable bar set."""
        counts: dict[UUID, int] = {o.option_id: 0 for o in self.options}
        for chosen in self._responses.values():
            counts[chosen] = counts.get(chosen, 0) + 1
        return counts

    def correct_count(self) -> int:
        """How many responses matched the key (quiz only)."""
        if self.kind is not QuestionKind.QUIZ or self.correct_option_id is None:
            return 0
        return sum(1 for opt in self._responses.values() if opt == self.correct_option_id)

    def grasp_ratio(self) -> float | None:
        """Fraction of respondents who got it right (quiz only). None for a poll,
        or when no one has responded yet."""
        if self.kind is not QuestionKind.QUIZ:
            return None
        if not self._responses:
            return None
        return self.correct_count() / len(self._responses)

    def is_correct(self, participant_ref: UUID) -> bool:
        if self.kind is not QuestionKind.QUIZ or self.correct_option_id is None:
            return False
        return self._responses.get(participant_ref) == self.correct_option_id


# ---------------------------------------------------------------------------
# Quiz: a sequence of questions with a leaderboard across them.
# ---------------------------------------------------------------------------
@dataclass
class LeaderboardRow:
    participant_ref: UUID
    correct: int
    answered: int

    @property
    def accuracy(self) -> float:
        return self.correct / self.answered if self.answered else 0.0


@dataclass
class LiveQuiz:
    """An ordered set of quiz questions linked to a lesson, with a leaderboard.

    The leaderboard is by OPAQUE participant ref; the surface resolves names under
    consent. Ranking is stable: more correct first, then fewer answered (efficiency
    tie-break), then ref order for determinism."""

    quiz_id: UUID
    ontology: OntologyRef | None = None
    questions: list[LiveQuestion] = field(default_factory=list)

    @classmethod
    def new(cls, *, ontology: OntologyRef | None = None, quiz_id: UUID | None = None) -> "LiveQuiz":
        return cls(quiz_id=quiz_id or uuid4(), ontology=ontology)

    def add_question(self, question: LiveQuestion) -> LiveQuestion:
        if question.kind is not QuestionKind.QUIZ:
            raise ValueError("a quiz holds quiz questions only")
        # Inherit the quiz's lesson link if the question did not set one.
        if question.ontology is None:
            question.ontology = self.ontology
        self.questions.append(question)
        return question

    def leaderboard(self) -> list[LeaderboardRow]:
        agg: dict[UUID, LeaderboardRow] = {}
        for q in self.questions:
            for ref, opt in q._responses.items():
                row = agg.setdefault(ref, LeaderboardRow(participant_ref=ref, correct=0, answered=0))
                row.answered += 1
                if opt == q.correct_option_id:
                    row.correct += 1
        rows = list(agg.values())
        rows.sort(key=lambda r: (-r.correct, r.answered, r.participant_ref.int))
        return rows

    def grasp_by_question(self) -> dict[UUID, float | None]:
        """Per-question grasp ratio — the teacher's "what was grasped" view."""
        return {q.question_id: q.grasp_ratio() for q in self.questions}


def make_options(labels: Iterable[str]) -> tuple[Option, ...]:
    """Helper to build options with fresh ids in order."""
    return tuple(Option(option_id=uuid4(), label=label) for label in labels)
