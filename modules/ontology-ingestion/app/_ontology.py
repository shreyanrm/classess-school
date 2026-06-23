"""The ontology graph types and snapshot, mirrored from the contract.

The canonical contract is ``contracts/src/ontology/types.ts`` (zod) — board
→ grade → subject → unit → chapter → topic → outcome → competency, plus a
prerequisite ``Edge`` (topic → topic, ``confirmed`` until a steward validates)
and a ``CrossBoardEquivalence`` reference. The behavioural pipeline is Python,
so this module is the faithful Python shape of those nodes. It is the single
internal source of truth the ingest / steward / equivalence / embeddings code
maps into — nothing here is keyed to any one board (BOARD-AGNOSTIC: the board is
a labelled node, never a baked-in enum).

INVARIANTS honoured by the SHAPES here:
  - Board is a FIELD, not an enum — :class:`Board` carries a ``code`` label.
  - A prerequisite :class:`Edge` starts ``confirmed = False`` and is never
    trusted for routing until a human steward confirms it.
  - Nodes carry NO PII — only opaque ids, kinds, names, and statements.

Import-safe: pure dataclasses + an enum. No I/O, no provider, no env read.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class NodeKind(str, Enum):
    """The kinds of node in the ontology graph, finest-to-coarsest aware.

    Mirrors ``OntologyNodeKind`` in the contract. Used to tag a node and to
    validate that ingestion / equivalence connect the levels they may.
    """

    BOARD = "board"
    GRADE = "grade"
    SUBJECT = "subject"
    UNIT = "unit"
    CHAPTER = "chapter"
    TOPIC = "topic"
    OUTCOME = "outcome"
    COMPETENCY = "competency"
    # Finer kinds below competency, completing the doc's full chain
    # (… competency → skill → question → resource).
    SKILL = "skill"
    QUESTION = "question"
    RESOURCE = "resource"


# The container chain from coarsest to finest. Ingestion walks this to place a
# node under its parent; it is ORDER, not a board assumption.
CONTAINER_ORDER: tuple[NodeKind, ...] = (
    NodeKind.BOARD,
    NodeKind.GRADE,
    NodeKind.SUBJECT,
    NodeKind.UNIT,
    NodeKind.CHAPTER,
    NodeKind.TOPIC,
    NodeKind.OUTCOME,
)


class PrerequisiteKind(str, Enum):
    """Why a prerequisite edge exists (mirrors the contract)."""

    HARD = "hard"  # the later topic cannot be attempted without the earlier one
    SOFT = "soft"  # easier with the earlier one, but not blocked


@dataclass(frozen=True)
class Board:
    id: str
    code: str  # short stable handle — a label, NEVER a board lock-in.
    name: str
    region: str | None = None
    kind: NodeKind = NodeKind.BOARD


@dataclass(frozen=True)
class Grade:
    id: str
    board_id: str
    level: int
    name: str
    kind: NodeKind = NodeKind.GRADE


@dataclass(frozen=True)
class Subject:
    id: str
    grade_id: str
    name: str
    kind: NodeKind = NodeKind.SUBJECT


@dataclass(frozen=True)
class Unit:
    id: str
    subject_id: str
    name: str
    sequence: int
    kind: NodeKind = NodeKind.UNIT


@dataclass(frozen=True)
class Chapter:
    id: str
    unit_id: str
    name: str
    sequence: int
    kind: NodeKind = NodeKind.CHAPTER


@dataclass(frozen=True)
class Topic:
    id: str
    chapter_id: str
    name: str
    sequence: int
    kind: NodeKind = NodeKind.TOPIC


@dataclass(frozen=True)
class Outcome:
    id: str
    topic_id: str
    statement: str
    kind: NodeKind = NodeKind.OUTCOME


@dataclass(frozen=True)
class Competency:
    id: str
    subject_id: str
    name: str
    statement: str
    outcome_ids: tuple[str, ...] = ()
    kind: NodeKind = NodeKind.COMPETENCY


@dataclass(frozen=True)
class Skill:
    """A skill below a competency — the doing that a competency is made of.

    A competency is demonstrated through one or more skills (e.g. "factorise a
    quadratic"). A skill references the competency it serves and the outcomes it
    operationalises, so coverage can be traced both ways. Carries NO PII.
    """

    id: str
    competency_id: str
    name: str
    statement: str
    outcome_ids: tuple[str, ...] = ()
    kind: NodeKind = NodeKind.SKILL


@dataclass(frozen=True)
class Question:
    """A question that assesses a skill (and, transitively, an outcome).

    The doc: "this question assesses that outcome". A question is the finest
    assessable node; it references the skill it exercises and the outcome it
    targets. ``stem`` is neutral curriculum text — never learner PII, never a
    learner's answer.
    """

    id: str
    skill_id: str
    stem: str
    outcome_id: str | None = None
    difficulty: str = "medium"  # "easy" | "medium" | "hard" — a label, not a score.
    kind: NodeKind = NodeKind.QUESTION


@dataclass(frozen=True)
class Resource:
    """A learning resource attached to the graph (the finest node kind).

    A resource (note, video, worksheet) is tagged to the ontology so a teacher
    sees everything relevant to a node in one view. ``resource_ref`` is an opaque
    content-store handle — NEVER the bytes, never PII. It may hang off a topic,
    skill, or question (whichever it best serves).
    """

    id: str
    target_id: str          # opaque id of the node it is attached to.
    target_kind: NodeKind   # topic | skill | question — what it serves.
    title: str
    resource_ref: str       # opaque content-store handle, never the content.
    media_type: str = "note"  # "note" | "video" | "worksheet" | "presentation".
    kind: NodeKind = NodeKind.RESOURCE


@dataclass(frozen=True)
class CompetitiveExamMapping:
    """Maps an ontology node to a competitive-exam syllabus reference.

    Board curriculum is not the only frame: a topic/outcome may also be examined
    by a competitive exam (entrance / scholarship / olympiad). The exam is a CODE
    label (board-agnostic in the same spirit — no exam is baked into the code).
    Carries a confidence + method for the confidence gate and explainability.
    """

    id: str
    node_id: str
    node_kind: NodeKind
    exam_code: str          # e.g. "example-entrance-exam" — a neutral label.
    syllabus_ref: str       # the exam's own syllabus handle/label.
    weight: float = 1.0     # how heavily the exam emphasises this node.
    confidence: float = 1.0
    confirmed: bool = False  # a proposal until a steward confirms it.


@dataclass(frozen=True)
class LocalOverlay:
    """A school-defined overlay on top of a node, NEVER mutating the base graph.

    A school adds local context — a renamed/aliased label, a re-sequencing, an
    emphasis flag, a local note — without forking the shared ontology. Overlays
    are keyed by an opaque ``scope_ref`` (the school/tenant) so the base node is
    identical for everyone; the overlay is applied as a projection. No PII.
    """

    id: str
    scope_ref: str          # opaque tenant/school ref — never a school name.
    node_id: str
    node_kind: NodeKind
    overlay_kind: str       # "alias" | "resequence" | "emphasis" | "note" | "hidden".
    value: str              # the alias text / note / sequence-as-string / flag.


@dataclass(frozen=True)
class CurriculumVersion:
    """A point-in-time version stamp for a curriculum scope.

    Curriculum is versioned (the doc): when a board revises a syllabus, a new
    version is recorded with an effective date, so coverage and routing can pin to
    a version. ``scope_id`` is the subject (or grade) the version applies to.
    Append-only by convention — a new revision is a new record, never an edit.
    """

    id: str
    scope_id: str           # the subject/grade the version applies to.
    scope_kind: NodeKind
    version: str            # e.g. "2024.1" — an opaque label, monotonic by date.
    effective_from: str     # ISO date string.
    note: str = ""
    supersedes_id: str | None = None


@dataclass(frozen=True)
class Edge:
    """A prerequisite edge, topic -> topic.

    An OWNED, expert-validated artifact: ``confirmed`` is ``False`` until a
    human steward confirms it. Proposed edges are NEVER trusted for routing.
    """

    id: str
    from_topic_id: str
    to_topic_id: str
    kind: PrerequisiteKind
    confirmed: bool
    rationale: str


@dataclass(frozen=True)
class CrossBoardEquivalence:
    """Maps a node in this ontology to the conceptually equivalent node in
    another board's ontology — so evidence travels across boards without the
    platform hard-coding any board. The other board is a ``code`` label."""

    id: str
    node_id: str
    node_kind: NodeKind
    equivalent_board_code: str
    equivalent_label: str
    confidence: float
    equivalent_node_id: str | None = None


@dataclass
class OntologySnapshot:
    """A flat set of typed node tables plus edges and equivalences. Projections
    build trees from it as needed. Mirrors the contract ``OntologySnapshot``."""

    board: Board
    grades: list[Grade] = field(default_factory=list)
    subjects: list[Subject] = field(default_factory=list)
    units: list[Unit] = field(default_factory=list)
    chapters: list[Chapter] = field(default_factory=list)
    topics: list[Topic] = field(default_factory=list)
    outcomes: list[Outcome] = field(default_factory=list)
    competencies: list[Competency] = field(default_factory=list)
    skills: list[Skill] = field(default_factory=list)
    questions: list[Question] = field(default_factory=list)
    resources: list[Resource] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    equivalences: list[CrossBoardEquivalence] = field(default_factory=list)
    exam_mappings: list[CompetitiveExamMapping] = field(default_factory=list)
    overlays: list[LocalOverlay] = field(default_factory=list)
    versions: list[CurriculumVersion] = field(default_factory=list)

    def topic_ids(self) -> set[str]:
        return {t.id for t in self.topics}

    def topic_by_id(self, topic_id: str) -> Topic | None:
        for t in self.topics:
            if t.id == topic_id:
                return t
        return None

    def outcome_ids(self) -> set[str]:
        return {o.id for o in self.outcomes}

    def node_ids(self) -> set[str]:
        """Every node id across all kinds — for overlay / mapping integrity."""
        ids: set[str] = {self.board.id}
        for table in (
            self.grades, self.subjects, self.units, self.chapters, self.topics,
            self.outcomes, self.competencies, self.skills, self.questions,
            self.resources,
        ):
            ids.update(n.id for n in table)
        return ids
