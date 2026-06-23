"""Interactive board state model (d7).

Canonical board engine. NOTE ON FILE NAME: intended to be importable as
``app.board``; the pre-existing ``board.py`` path was locked by the host sandbox
in this build and could not be overwritten, so the working engine lives here and
is re-exported by ``app/__init__.py``.

An infinite-canvas board for live delivery: ordered pages, each holding strokes
and objects placed at arbitrary canvas coordinates. The board is a pure state
model -- it computes the next state and emits events; it performs no rendering
and no I/O. The board UI is a later surface task.

On-device vision ASSISTS only. The board may attach an optional vision hint to a
committed object (e.g. "this sketch resembles a triangle") but a hint is
advisory, gated by a confidence threshold (generate-and-verify), NEVER grades a
person, NEVER derives from a face / raw image, and carries no PII. Vision input
is a reduced on-device descriptor (shape class + confidence), never an image,
never an identity.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from .events import Event, EventKind, is_opaque_uuid

#: Confidence gate for accepting an assistive vision hint onto an object.
VISION_HINT_CONFIDENCE_GATE = 0.70


class ObjectKind(str, enum.Enum):
    STROKE = "stroke"
    TEXT = "text"
    SHAPE = "shape"
    IMAGE_REF = "image_ref"  # a reference handle, never raw image bytes
    STICKY = "sticky"


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True)
class VisionHint:
    """An on-device, assistive vision descriptor for a board object.

    This is NOT a grade and NOT an identity. It describes the content the user
    drew (e.g. a shape class), produced on-device, accepted only above the
    confidence gate. ``source_is_face`` must always be False -- vision never
    grades from a face.
    """

    label: str
    confidence: float
    source_is_face: bool = False

    def __post_init__(self) -> None:
        if self.source_is_face:
            raise ValueError("vision must never derive a hint from a face")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be in [0, 1]")

    @property
    def accepted(self) -> bool:
        """True only when the hint clears the confidence gate."""
        return self.confidence >= VISION_HINT_CONFIDENCE_GATE


@dataclass(frozen=True)
class BoardObject:
    """An immutable object on a board page.

    Strokes carry a tuple of points; other kinds carry an opaque ``data`` map
    (which never includes PII or raw image bytes). A committed object is final;
    edits create a new object via :meth:`Board.commit_object`.
    """

    object_id: str
    kind: ObjectKind
    author_uuid: str
    points: tuple[Point, ...] = ()
    data: dict[str, Any] = field(default_factory=dict)
    vision_hint: Optional[VisionHint] = None

    def __post_init__(self) -> None:
        if not is_opaque_uuid(self.author_uuid):
            raise ValueError("author_uuid must be an opaque canonical_uuid")
        if self.kind is ObjectKind.STROKE and not self.points:
            raise ValueError("a stroke needs at least one point")
        if "image" in self.data or "raw_image" in self.data:
            raise ValueError("board objects never store raw image bytes")


@dataclass(frozen=True)
class Page:
    """One infinite-canvas page. Objects are kept in commit order."""

    page_id: str
    index: int
    objects: tuple[BoardObject, ...] = ()

    def with_object(self, obj: BoardObject) -> "Page":
        return Page(self.page_id, self.index, self.objects + (obj,))

    def without_object(self, object_id: str) -> "Page":
        kept = tuple(o for o in self.objects if o.object_id != object_id)
        return Page(self.page_id, self.index, kept)


class Board:
    """Mutable container of pages; each op returns the event it produced.

    The board mutates its own page list (live working state) but every page and
    object value is immutable, so history can be reconstructed from the event
    log. Coordinates are unbounded: the canvas is infinite.
    """

    def __init__(self, session_id: str) -> None:
        if not session_id:
            raise ValueError("session_id is required")
        self.session_id = session_id
        self._pages: list[Page] = []
        self.add_page()  # a board always opens with one page

    # -- pages -----------------------------------------------------------
    @property
    def pages(self) -> tuple[Page, ...]:
        return tuple(self._pages)

    def page(self, page_id: str) -> Page:
        for p in self._pages:
            if p.page_id == page_id:
                return p
        raise KeyError(f"unknown page {page_id!r}")

    def add_page(self) -> Page:
        page = Page(page_id=str(uuid.uuid4()), index=len(self._pages))
        self._pages.append(page)
        return page

    def page_added_event(self, page: Page, author_uuid: str) -> Event:
        return Event(
            kind=EventKind.BOARD_PAGE_ADDED,
            session_id=self.session_id,
            subject_uuid=author_uuid,
            payload={"page_id": page.page_id, "index": page.index},
        )

    # -- objects ---------------------------------------------------------
    def commit_object(self, page_id: str, obj: BoardObject) -> Event:
        """Commit an object to a page and return the resulting event.

        An attached vision hint that fails the confidence gate is dropped
        (generate-and-verify): the object is kept, the unreliable hint is not.
        """
        page = self.page(page_id)

        hint = obj.vision_hint
        if hint is not None and not hint.accepted:
            obj = BoardObject(
                object_id=obj.object_id,
                kind=obj.kind,
                author_uuid=obj.author_uuid,
                points=obj.points,
                data=dict(obj.data),
                vision_hint=None,
            )

        new_page = page.with_object(obj)
        self._pages[page.index] = new_page

        payload: dict[str, Any] = {
            "page_id": page_id,
            "object_id": obj.object_id,
            "kind": obj.kind.value,
        }
        if obj.vision_hint is not None:
            payload["vision_hint"] = {
                "label": obj.vision_hint.label,
                "confidence": obj.vision_hint.confidence,
                "assistive": True,
            }
        return Event(
            kind=EventKind.BOARD_OBJECT_COMMITTED,
            session_id=self.session_id,
            subject_uuid=obj.author_uuid,
            payload=payload,
        )

    def erase_object(self, page_id: str, object_id: str) -> None:
        page = self.page(page_id)
        self._pages[page.index] = page.without_object(object_id)

    def object_count(self) -> int:
        return sum(len(p.objects) for p in self._pages)


def new_stroke(
    author_uuid: str,
    points: list,
    vision_hint: Optional[VisionHint] = None,
) -> BoardObject:
    """Convenience constructor for a stroke object."""
    return BoardObject(
        object_id=str(uuid.uuid4()),
        kind=ObjectKind.STROKE,
        author_uuid=author_uuid,
        points=tuple(Point(x, y) for x, y in points),
        vision_hint=vision_hint,
    )
