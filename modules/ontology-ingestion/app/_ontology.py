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
    edges: list[Edge] = field(default_factory=list)
    equivalences: list[CrossBoardEquivalence] = field(default_factory=list)

    def topic_ids(self) -> set[str]:
        return {t.id for t in self.topics}

    def topic_by_id(self, topic_id: str) -> Topic | None:
        for t in self.topics:
            if t.id == topic_id:
                return t
        return None
