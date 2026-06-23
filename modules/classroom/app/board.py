"""Interactive board state model (D7).

The board is an infinite-canvas, multi-page teaching surface. This module is the
ENGINE/STATE for that surface: pages on an unbounded canvas, ink strokes, and
placed objects (text, shapes, images, embedded content). The native interactive
panel (fast native ink over a hardware-accelerated content host) is a later
surface task; this is the deterministic, testable state it drives.

Design rules held here:

  - Append-then-resolve ops. Every mutation is an ``BoardOp`` applied to produce a
    NEW immutable snapshot; the op log is the source of truth, so the board can be
    synced over a realtime channel and replayed deterministically. Undo/redo is a
    cursor over that log, never an in-place edit.
  - Infinite canvas: page bounds are computed from content, not fixed. Pan/zoom is
    a viewport over the canvas; content coordinates are unbounded floats.
  - ON-DEVICE VISION ASSISTS ONLY. ``VisionAssist`` carries hints — a detected
    shape to snap, handwriting-to-text suggestions, a "tidy this diagram" prompt —
    that the TEACHER accepts or rejects. The board NEVER auto-applies a vision
    suggestion, NEVER grades from a face, and NEVER ingests a face/identity signal.
    Vision assists carry no ``canonical_uuid`` and no PII; they describe canvas
    geometry only. Acceptance is an explicit op (human authority).

No PII anywhere: a stroke/object author is an opaque participant ref. No I/O,
no realtime client, no vision runtime is required — the model is pure.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Iterable
from uuid import UUID, uuid4


# ---------------------------------------------------------------------------
# Primitive geometry on the infinite canvas (unbounded floats).
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True)
class BBox:
    """Axis-aligned bounds. ``empty`` is the identity for ``union``."""

    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @classmethod
    def empty(cls) -> "BBox":
        return cls(float("inf"), float("inf"), float("-inf"), float("-inf"))

    @property
    def is_empty(self) -> bool:
        return self.min_x > self.max_x or self.min_y > self.max_y

    @property
    def width(self) -> float:
        return 0.0 if self.is_empty else self.max_x - self.min_x

    @property
    def height(self) -> float:
        return 0.0 if self.is_empty else self.max_y - self.min_y

    def union(self, other: "BBox") -> "BBox":
        if self.is_empty:
            return other
        if other.is_empty:
            return self
        return BBox(
            min(self.min_x, other.min_x),
            min(self.min_y, other.min_y),
            max(self.max_x, other.max_x),
            max(self.max_y, other.max_y),
        )

    @classmethod
    def of_points(cls, points: Iterable[Point]) -> "BBox":
        box = cls.empty()
        for p in points:
            box = box.union(BBox(p.x, p.y, p.x, p.y))
        return box


# ---------------------------------------------------------------------------
# Board content elements.
# ---------------------------------------------------------------------------
class ObjectKind(str, Enum):
    TEXT = "text"
    SHAPE = "shape"
    IMAGE = "image"
    EMBED = "embed"  # embedded content host (a slide, a sim, a document)


@dataclass(frozen=True)
class Stroke:
    """A single ink stroke. ``author_ref`` is an opaque participant ref (never PII)."""

    stroke_id: UUID
    points: tuple[Point, ...]
    color: str = "#1f2933"  # design-system ink default; not the ultramarine brand mark
    width: float = 2.0
    author_ref: UUID | None = None

    def bbox(self) -> BBox:
        return BBox.of_points(self.points)


@dataclass(frozen=True)
class BoardObject:
    """A placed, non-ink object on the canvas."""

    object_id: UUID
    kind: ObjectKind
    at: Point
    width: float
    height: float
    content_ref: str | None = None  # opaque ref to text/image/embed payload
    author_ref: UUID | None = None

    def bbox(self) -> BBox:
        return BBox(self.at.x, self.at.y, self.at.x + self.width, self.at.y + self.height)


@dataclass(frozen=True)
class Page:
    """One infinite-canvas page. Bounds are derived from content, not fixed."""

    page_id: UUID
    index: int
    strokes: tuple[Stroke, ...] = ()
    objects: tuple[BoardObject, ...] = ()

    def content_bounds(self) -> BBox:
        box = BBox.empty()
        for s in self.strokes:
            box = box.union(s.bbox())
        for o in self.objects:
            box = box.union(o.bbox())
        return box


# ---------------------------------------------------------------------------
# On-device vision assist — HINTS ONLY. Never auto-applied, never identity.
# ---------------------------------------------------------------------------
class VisionAssistKind(str, Enum):
    SHAPE_SNAP = "shape_snap"           # "this freehand circle could snap to a circle"
    HANDWRITING_TO_TEXT = "handwriting_to_text"  # suggested text for an ink region
    DIAGRAM_TIDY = "diagram_tidy"       # suggested alignment of a diagram


@dataclass(frozen=True)
class VisionAssist:
    """An assistive suggestion from on-device vision about CANVAS GEOMETRY.

    It carries no person reference, no face data, no ``canonical_uuid`` — only a
    target region and a suggested transform. The teacher accepts or rejects it;
    the board never auto-applies it. ``accepted`` defaults to False (HUMAN
    AUTHORITY — a consequential edit is never auto-fired).
    """

    assist_id: UUID
    kind: VisionAssistKind
    target_bbox: BBox
    suggestion: str            # plain-language description of the proposed change
    confidence: float          # [0,1] on-device confidence in the geometry hint
    accepted: bool = False

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0,1].")
        # Guardrail: a vision assist must describe geometry, not a person. We
        # forbid any obvious identity/face token in the suggestion text.
        lowered = self.suggestion.lower()
        for banned in ("face", "identity", "who is", "recognize", "recognise"):
            if banned in lowered:
                raise ValueError(
                    "Vision assist describes canvas geometry only; "
                    "it never references a face or identity."
                )


# ---------------------------------------------------------------------------
# Ops — every mutation is an op applied to produce a new snapshot.
# ---------------------------------------------------------------------------
class OpKind(str, Enum):
    ADD_PAGE = "add_page"
    ADD_STROKE = "add_stroke"
    ADD_OBJECT = "add_object"
    ERASE_STROKE = "erase_stroke"
    REMOVE_OBJECT = "remove_object"
    CLEAR_PAGE = "clear_page"
    ACCEPT_VISION_ASSIST = "accept_vision_assist"


@dataclass(frozen=True)
class BoardOp:
    """One immutable mutation. The op log is the source of truth and is replayable
    deterministically; sync sends ops, not whole-board diffs."""

    op_id: UUID
    kind: OpKind
    page_id: UUID | None = None
    stroke: Stroke | None = None
    object: BoardObject | None = None
    target_id: UUID | None = None
    page_index: int | None = None


@dataclass(frozen=True)
class BoardState:
    """An immutable board snapshot. Apply an op to get a new snapshot."""

    board_id: UUID
    pages: tuple[Page, ...] = ()

    # -- queries -----------------------------------------------------------
    def page(self, page_id: UUID) -> Page:
        for p in self.pages:
            if p.page_id == page_id:
                return p
        raise KeyError(f"page {page_id} not on board")

    def canvas_bounds(self) -> BBox:
        """Bounds across all pages — the infinite canvas's used extent."""
        box = BBox.empty()
        for p in self.pages:
            box = box.union(p.content_bounds())
        return box

    # -- apply -------------------------------------------------------------
    def apply(self, op: BoardOp) -> "BoardState":
        """Return a NEW state with the op applied. Never mutates in place."""
        if op.kind is OpKind.ADD_PAGE:
            idx = op.page_index if op.page_index is not None else len(self.pages)
            new_page = Page(page_id=op.page_id or uuid4(), index=idx)
            return replace(self, pages=self.pages + (new_page,))

        if op.kind is OpKind.ACCEPT_VISION_ASSIST:
            # Acceptance is recorded as an explicit human op. The geometric effect
            # of a specific assist is materialised by the caller as concrete
            # ADD/ERASE ops; this op marks human authority over that change.
            return self

        # All remaining ops target a page.
        if op.page_id is None:
            raise ValueError(f"{op.kind} requires page_id")
        pages = list(self.pages)
        for i, p in enumerate(pages):
            if p.page_id != op.page_id:
                continue
            pages[i] = self._apply_to_page(p, op)
            return replace(self, pages=tuple(pages))
        raise KeyError(f"page {op.page_id} not on board")

    @staticmethod
    def _apply_to_page(page: Page, op: BoardOp) -> Page:
        if op.kind is OpKind.ADD_STROKE:
            if op.stroke is None:
                raise ValueError("ADD_STROKE requires a stroke")
            return replace(page, strokes=page.strokes + (op.stroke,))
        if op.kind is OpKind.ADD_OBJECT:
            if op.object is None:
                raise ValueError("ADD_OBJECT requires an object")
            return replace(page, objects=page.objects + (op.object,))
        if op.kind is OpKind.ERASE_STROKE:
            kept = tuple(s for s in page.strokes if s.stroke_id != op.target_id)
            return replace(page, strokes=kept)
        if op.kind is OpKind.REMOVE_OBJECT:
            kept = tuple(o for o in page.objects if o.object_id != op.target_id)
            return replace(page, objects=kept)
        if op.kind is OpKind.CLEAR_PAGE:
            return replace(page, strokes=(), objects=())
        raise ValueError(f"unknown page op {op.kind}")


# ---------------------------------------------------------------------------
# The board document: state + op log + undo/redo cursor.
# ---------------------------------------------------------------------------
@dataclass
class BoardDocument:
    """A live board: the current snapshot plus its replayable op log.

    Undo/redo is a cursor over the committed-op history; a redo branch is
    discarded when a new op is committed after an undo (standard editor model).
    The op log is what a realtime channel would carry (set
    ``clss.classroom.dev.realtime_url`` to fan it out).
    """

    state: BoardState
    _history: list[BoardOp] = field(default_factory=list)
    _cursor: int = 0  # number of applied ops from history head

    @classmethod
    def new(cls, board_id: UUID | None = None) -> "BoardDocument":
        return cls(state=BoardState(board_id=board_id or uuid4()))

    @property
    def op_log(self) -> tuple[BoardOp, ...]:
        """The committed ops up to the current cursor — the sync/replay log."""
        return tuple(self._history[: self._cursor])

    def commit(self, op: BoardOp) -> BoardState:
        """Apply + record an op. Truncates any undone (redo) tail first."""
        # Validate the op against the live state before recording it.
        new_state = self.state.apply(op)
        del self._history[self._cursor :]
        self._history.append(op)
        self._cursor += 1
        self.state = new_state
        return self.state

    @property
    def can_undo(self) -> bool:
        return self._cursor > 0

    @property
    def can_redo(self) -> bool:
        return self._cursor < len(self._history)

    def undo(self) -> BoardState:
        """Step the cursor back and rebuild the snapshot by replay."""
        if not self.can_undo:
            return self.state
        self._cursor -= 1
        self.state = self._replay(self._history[: self._cursor])
        return self.state

    def redo(self) -> BoardState:
        if not self.can_redo:
            return self.state
        self._cursor += 1
        self.state = self._replay(self._history[: self._cursor])
        return self.state

    def _replay(self, ops: list[BoardOp]) -> BoardState:
        state = BoardState(board_id=self.state.board_id)
        for op in ops:
            state = state.apply(op)
        return state


# ---------------------------------------------------------------------------
# Convenience op builders.
# ---------------------------------------------------------------------------
def add_page_op(*, index: int | None = None, page_id: UUID | None = None) -> BoardOp:
    return BoardOp(op_id=uuid4(), kind=OpKind.ADD_PAGE, page_id=page_id, page_index=index)


def add_stroke_op(page_id: UUID, stroke: Stroke) -> BoardOp:
    return BoardOp(op_id=uuid4(), kind=OpKind.ADD_STROKE, page_id=page_id, stroke=stroke)


def add_object_op(page_id: UUID, obj: BoardObject) -> BoardOp:
    return BoardOp(op_id=uuid4(), kind=OpKind.ADD_OBJECT, page_id=page_id, object=obj)


def erase_stroke_op(page_id: UUID, stroke_id: UUID) -> BoardOp:
    return BoardOp(op_id=uuid4(), kind=OpKind.ERASE_STROKE, page_id=page_id, target_id=stroke_id)


def remove_object_op(page_id: UUID, object_id: UUID) -> BoardOp:
    return BoardOp(op_id=uuid4(), kind=OpKind.REMOVE_OBJECT, page_id=page_id, target_id=object_id)


def clear_page_op(page_id: UUID) -> BoardOp:
    return BoardOp(op_id=uuid4(), kind=OpKind.CLEAR_PAGE, page_id=page_id)
