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

#: Confidence gate below which subject-aware generated content is NOT shown live
#: (generate-and-verify): a content ref under the gate is staged, never surfaced.
CONTENT_VERIFY_CONFIDENCE_GATE = 0.75

#: Sentinel distinguishing "argument not passed" from an explicit ``None``.
_UNSET: Any = object()


class ObjectKind(str, enum.Enum):
    STROKE = "stroke"
    TEXT = "text"
    SHAPE = "shape"
    IMAGE_REF = "image_ref"  # a reference handle, never raw image bytes
    STICKY = "sticky"
    DOCUMENT_REF = "document_ref"  # a shared document handle (no raw bytes)
    # Subject-aware teaching content references. The board carries a TYPED ref +
    # per-session generate-and-verify metadata only; actual media rendering is a
    # later surface task (deferred). The ref never holds raw media bytes.
    MODEL_3D = "model_3d"  # a 3D explorable model reference
    SIMULATION = "simulation"  # an interactive simulation reference
    ANIMATED_EXPLANATION = "animated_explanation"  # an animated explainer ref


#: Object kinds that are subject-aware generated teaching content. Committing one
#: requires per-session generate-and-verify metadata that clears the gate.
GENERATED_CONTENT_KINDS = frozenset(
    {ObjectKind.MODEL_3D, ObjectKind.SIMULATION, ObjectKind.ANIMATED_EXPLANATION}
)


class BoardTheme(str, enum.Enum):
    """Selectable board themes (a calm, neutral palette; no brand marks)."""

    LIGHT = "light"
    DARK = "dark"
    CHALK = "chalk"  # dark surface, light ink
    GRID = "grid"  # light surface with a grid
    DOTTED = "dotted"  # light surface with a dot grid


class ToolKind(str, enum.Enum):
    """The active drawing/shape tool model for the board.

    A tool describes HOW the next stroke/object is authored; it is pure state
    (selection), it performs no rendering. ``SELECT`` and ``ERASER`` manipulate
    existing objects; the rest author new ones.
    """

    PEN = "pen"
    HIGHLIGHTER = "highlighter"
    LINE = "line"
    RECTANGLE = "rectangle"
    ELLIPSE = "ellipse"
    ARROW = "arrow"
    TEXT = "text"
    ERASER = "eraser"
    SELECT = "select"


#: Tools that author a SHAPE object (vs. a freehand stroke or a manipulation).
SHAPE_TOOLS = frozenset(
    {ToolKind.LINE, ToolKind.RECTANGLE, ToolKind.ELLIPSE, ToolKind.ARROW}
)


@dataclass(frozen=True)
class ContentVerification:
    """Per-session generate-and-verify metadata for subject-aware content.

    Subject-aware teaching content (3D model / simulation / animated explanation)
    is GENERATED for the topic taught this session and VERIFIED before it may be
    shown live. ``confidence`` is the verifier's confidence the content matches
    the topic; ``cross_checked`` records that a second model agreed (the doc's
    cross-check). Content below the gate is staged, never surfaced.
    """

    topic: str
    confidence: float
    cross_checked: bool = False
    verifier: str = "on_device"

    def __post_init__(self) -> None:
        if not self.topic:
            raise ValueError("generated content must name the topic it teaches")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be in [0, 1]")

    @property
    def verified(self) -> bool:
        """True only when the content clears the verify gate (show-live ready)."""
        return self.confidence >= CONTENT_VERIFY_CONFIDENCE_GATE


@dataclass(frozen=True)
class ContentInteraction:
    """Per-session interaction state for a subject-aware content object.

    A 3D model is EXPLORABLE, a simulation is INTERACTIVE, an animated explanation
    PLAYS -- but the actual media rendering is a later surface task (deferred). What
    is modelled here is the deterministic, replayable INTERACTION STATE the teacher
    drives: a named viewpoint / step, plus opaque parameter knobs. It holds no raw
    media, no PII, and no identity -- only the topic-scoped control state. The
    surface reads this state to render; this engine never renders.
    """

    #: A named viewpoint (3D), step (animation), or scenario (simulation).
    viewpoint: str = "default"
    #: Opaque, JSON-safe parameter knobs (e.g. {"rotation_deg": 90}); never PII.
    params: dict[str, Any] = field(default_factory=dict)
    #: Animation/sim step index; 0 for a static viewpoint.
    step: int = 0

    def __post_init__(self) -> None:
        if self.step < 0:
            raise ValueError("interaction step cannot be negative")
        if any(k in self.params for k in ("image", "raw_image", "raw_media", "bytes")):
            raise ValueError("interaction params never carry raw image/media bytes")

    def at(self, viewpoint: str, *, step: int | None = None, **params: Any) -> "ContentInteraction":
        """Return a new interaction state at ``viewpoint`` (pure; no mutation)."""
        merged = dict(self.params)
        merged.update(params)
        return ContentInteraction(
            viewpoint=viewpoint,
            params=merged,
            step=self.step if step is None else step,
        )


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
    #: Active tool that authored this object (advisory; pure state).
    tool: Optional[ToolKind] = None
    #: Per-session generate-and-verify metadata (subject-aware content only).
    verification: Optional[ContentVerification] = None
    #: Live interaction state for subject-aware content (viewpoint / step / params).
    #: Rendering is deferred; this is the deterministic control state the surface reads.
    interaction: Optional[ContentInteraction] = None

    def __post_init__(self) -> None:
        if not is_opaque_uuid(self.author_uuid):
            raise ValueError("author_uuid must be an opaque canonical_uuid")
        if self.kind is ObjectKind.STROKE and not self.points:
            raise ValueError("a stroke needs at least one point")
        if any(k in self.data for k in ("image", "raw_image", "raw_media", "bytes")):
            raise ValueError("board objects never store raw image/media bytes")
        if self.kind in GENERATED_CONTENT_KINDS and self.verification is None:
            raise ValueError(
                "subject-aware generated content requires per-session "
                "generate-and-verify metadata"
            )
        if self.interaction is not None and self.kind not in GENERATED_CONTENT_KINDS:
            raise ValueError(
                "interaction state is only for subject-aware generated content"
            )

    @property
    def is_generated_content(self) -> bool:
        return self.kind in GENERATED_CONTENT_KINDS

    def with_interaction(self, interaction: ContentInteraction) -> "BoardObject":
        """Return a copy of this content object at a new interaction state."""
        if self.kind not in GENERATED_CONTENT_KINDS:
            raise ValueError("only subject-aware content carries interaction state")
        return _replace_hint(self, self.vision_hint, interaction=interaction)


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

    def with_replaced_object(self, obj: BoardObject) -> "Page":
        """Replace the object with matching id IN PLACE (commit order preserved)."""
        swapped = tuple(obj if o.object_id == obj.object_id else o for o in self.objects)
        return Page(self.page_id, self.index, swapped)


@dataclass(frozen=True)
class FrozenFrame:
    """A frozen snapshot of a live page plus the annotations layered over it.

    Freeze-frame mode lets a teacher pause the live interaction and annotate a
    captured frame WITHOUT mutating the live page. Annotations accumulate on the
    frame; on resume the live page is restored untouched and the annotations may
    be kept as a record. The frame references a page snapshot by value -- it holds
    no raw image bytes (the visual capture is a surface concern, deferred).
    """

    page_id: str
    base_objects: tuple[BoardObject, ...]
    annotations: tuple[BoardObject, ...] = ()

    def with_annotation(self, obj: BoardObject) -> "FrozenFrame":
        return FrozenFrame(
            self.page_id, self.base_objects, self.annotations + (obj,)
        )

    def without_annotation(self, object_id: str) -> "FrozenFrame":
        kept = tuple(a for a in self.annotations if a.object_id != object_id)
        return FrozenFrame(self.page_id, self.base_objects, kept)

    def cleared(self) -> "FrozenFrame":
        """Drop all annotations, keeping the captured base frame."""
        return FrozenFrame(self.page_id, self.base_objects, ())


class Board:
    """Mutable container of pages; each op returns the event it produced.

    The board mutates its own page list (live working state) but every page and
    object value is immutable, so history can be reconstructed from the event
    log. Coordinates are unbounded: the canvas is infinite.
    """

    def __init__(self, session_id: str, theme: BoardTheme = BoardTheme.LIGHT) -> None:
        if not session_id:
            raise ValueError("session_id is required")
        self.session_id = session_id
        self.theme = theme
        self.active_tool = ToolKind.PEN
        self._pages: list[Page] = []
        #: Freeze-frame annotate mode. When frozen, the board overlays annotations
        #: on a captured frame snapshot instead of mutating the live page; the live
        #: page is preserved and restored on resume. ``None`` means live mode.
        self._frozen_frame: Optional[FrozenFrame] = None
        self.add_page()  # a board always opens with one page

    # -- themes ----------------------------------------------------------
    def set_theme(self, theme: BoardTheme, author_uuid: str) -> Event:
        """Switch the board theme. A presentation choice, not consequential."""
        if not is_opaque_uuid(author_uuid):
            raise ValueError("author_uuid must be an opaque canonical_uuid")
        self.theme = theme
        return Event(
            kind=EventKind.BOARD_THEME_CHANGED,
            session_id=self.session_id,
            subject_uuid=author_uuid,
            payload={"theme": theme.value},
        )

    # -- tool model ------------------------------------------------------
    def select_tool(self, tool: ToolKind) -> ToolKind:
        """Select the active drawing/shape tool (pure state, no event)."""
        self.active_tool = tool
        return self.active_tool

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

        Subject-aware generated content (3D / simulation / animated explanation)
        is gated by per-session verification: content that has not cleared the
        verify gate is REFUSED from the live board (generate-and-verify -- nothing
        unverified is shown). Stage + verify it first via :meth:`stage_content`.

        While a frame is frozen, a commit annotates the frozen frame instead of
        mutating the live page (freeze-frame annotate mode).
        """
        hint = obj.vision_hint
        if hint is not None and not hint.accepted:
            obj = _replace_hint(obj, None)

        if obj.is_generated_content and not (
            obj.verification and obj.verification.verified
        ):
            raise ValueError(
                "unverified subject-aware content cannot be shown live; "
                "stage and verify it first (generate-and-verify)"
            )

        if self._frozen_frame is not None:
            # Freeze-frame mode: layer the annotation on the frozen frame, leave
            # the live page untouched.
            self._frozen_frame = self._frozen_frame.with_annotation(obj)
        else:
            page = self.page(page_id)
            self._pages[page.index] = page.with_object(obj)

        payload: dict[str, Any] = {
            "page_id": page_id,
            "object_id": obj.object_id,
            "kind": obj.kind.value,
            "frozen": self._frozen_frame is not None,
        }
        if obj.tool is not None:
            payload["tool"] = obj.tool.value
        if obj.vision_hint is not None:
            payload["vision_hint"] = {
                "label": obj.vision_hint.label,
                "confidence": obj.vision_hint.confidence,
                "assistive": True,
            }
        if obj.verification is not None:
            payload["verified"] = obj.verification.verified
            payload["topic"] = obj.verification.topic
        return Event(
            kind=EventKind.BOARD_OBJECT_COMMITTED,
            session_id=self.session_id,
            subject_uuid=obj.author_uuid,
            payload=payload,
        )

    # -- subject-aware generated content ---------------------------------
    def stage_content(
        self, obj: BoardObject, page_id: Optional[str] = None
    ) -> tuple[bool, Event]:
        """Generate-and-verify a subject-aware content object before showing it.

        Returns ``(verified, event)``. The event records the verification outcome
        regardless; ``verified`` is True only when the content cleared the gate
        and was committed live. Unverified content is NOT placed on the board.
        ``page_id`` defaults to the first page.
        """
        if not obj.is_generated_content:
            raise ValueError("stage_content is for subject-aware generated content")
        if obj.verification is None:
            raise ValueError("generated content requires verification metadata")
        verified = obj.verification.verified
        event = Event(
            kind=EventKind.BOARD_CONTENT_VERIFIED,
            session_id=self.session_id,
            subject_uuid=obj.author_uuid,
            payload={
                "object_id": obj.object_id,
                "kind": obj.kind.value,
                "topic": obj.verification.topic,
                "confidence": obj.verification.confidence,
                "cross_checked": obj.verification.cross_checked,
                "verified": verified,
            },
        )
        if verified:
            self.commit_object(page_id or self._pages[0].page_id, obj)
        return verified, event

    def drive_content(
        self, page_id: str, object_id: str, interaction: ContentInteraction
    ) -> Event:
        """Move a committed subject-aware content object to a new interaction state.

        Explores a 3D model / steps an animation / sets a simulation scenario by
        replacing the object's interaction state in place (the object stays the
        same id). Rendering is deferred; this is the deterministic control state a
        surface would read. Refuses an object that is not subject-aware content.
        """
        page = self.page(page_id)
        for obj in page.objects:
            if obj.object_id != object_id:
                continue
            if not obj.is_generated_content:
                raise ValueError("only subject-aware content has interaction state")
            self._pages[page.index] = page.with_replaced_object(
                obj.with_interaction(interaction)
            )
            return Event(
                kind=EventKind.BOARD_CONTENT_INTERACTED,
                session_id=self.session_id,
                subject_uuid=obj.author_uuid,
                payload={
                    "page_id": page_id,
                    "object_id": object_id,
                    "kind": obj.kind.value,
                    "viewpoint": interaction.viewpoint,
                    "step": interaction.step,
                },
            )
        raise KeyError(f"unknown content object {object_id!r} on page {page_id!r}")

    # -- freeze-frame annotate mode --------------------------------------
    @property
    def is_frozen(self) -> bool:
        return self._frozen_frame is not None

    @property
    def frozen_frame(self) -> Optional["FrozenFrame"]:
        return self._frozen_frame

    def freeze_frame(self, page_id: str, author_uuid: str) -> Event:
        """Enter freeze-frame mode over a captured snapshot of ``page_id``.

        Subsequent commits annotate the frozen frame; the live page is preserved
        and restored on resume.
        """
        if not is_opaque_uuid(author_uuid):
            raise ValueError("author_uuid must be an opaque canonical_uuid")
        if self._frozen_frame is not None:
            raise RuntimeError("already in freeze-frame mode")
        page = self.page(page_id)
        self._frozen_frame = FrozenFrame(
            page_id=page.page_id, base_objects=page.objects
        )
        return Event(
            kind=EventKind.BOARD_FRAME_FROZEN,
            session_id=self.session_id,
            subject_uuid=author_uuid,
            payload={"page_id": page.page_id},
        )

    def resume_live(self, author_uuid: str, *, keep_annotations: bool = False) -> Event:
        """Exit freeze-frame mode back to live interaction.

        The live page is untouched by annotations made while frozen. If
        ``keep_annotations`` is set, the frame's annotations are merged onto the
        live page as a kept record; otherwise they are discarded.
        """
        if not is_opaque_uuid(author_uuid):
            raise ValueError("author_uuid must be an opaque canonical_uuid")
        if self._frozen_frame is None:
            raise RuntimeError("not in freeze-frame mode")
        frame = self._frozen_frame
        kept = 0
        if keep_annotations and frame.annotations:
            page = self.page(frame.page_id)
            merged = page
            for ann in frame.annotations:
                merged = merged.with_object(ann)
            self._pages[merged.index] = merged
            kept = len(frame.annotations)
        self._frozen_frame = None
        return Event(
            kind=EventKind.BOARD_FRAME_RESUMED,
            session_id=self.session_id,
            subject_uuid=author_uuid,
            payload={"page_id": frame.page_id, "annotations_kept": kept},
        )

    # -- document sharing ------------------------------------------------
    def share_document(
        self,
        page_id: str,
        author_uuid: str,
        document_ref: str,
        *,
        title: str = "",
    ) -> tuple[BoardObject, Event]:
        """Share a document onto the board as a typed reference object.

        ``document_ref`` is an opaque handle (e.g. a content-store id); raw
        document bytes are never carried here. Returns the placed object and the
        share event.
        """
        if not document_ref:
            raise ValueError("document_ref is required")
        obj = BoardObject(
            object_id=str(uuid.uuid4()),
            kind=ObjectKind.DOCUMENT_REF,
            author_uuid=author_uuid,
            data={"document_ref": document_ref, "title": title},
        )
        self.commit_object(page_id, obj)
        event = Event(
            kind=EventKind.BOARD_DOCUMENT_SHARED,
            session_id=self.session_id,
            subject_uuid=author_uuid,
            payload={
                "page_id": page_id,
                "object_id": obj.object_id,
                "document_ref": document_ref,
            },
        )
        return obj, event

    def erase_object(self, page_id: str, object_id: str) -> None:
        """Erase an object. While frozen, erases a FRAME ANNOTATION (the live page
        is never mutated in freeze-frame mode); otherwise erases from the live page."""
        if self._frozen_frame is not None:
            self._frozen_frame = self._frozen_frame.without_annotation(object_id)
            return
        page = self.page(page_id)
        self._pages[page.index] = page.without_object(object_id)

    def clear_annotations(self) -> None:
        """Drop every annotation on the current frozen frame (live page untouched).

        A no-op when not frozen. Lets a teacher wipe their freeze-frame markup and
        start the annotation over without disturbing the captured base frame.
        """
        if self._frozen_frame is not None:
            self._frozen_frame = self._frozen_frame.cleared()

    def object_count(self) -> int:
        return sum(len(p.objects) for p in self._pages)


def _replace_hint(
    obj: BoardObject,
    hint: Optional[VisionHint],
    *,
    interaction: Optional[ContentInteraction] = _UNSET,
) -> BoardObject:
    """Return a copy of ``obj`` with its vision hint (and optionally interaction
    state) replaced; no other field changes."""
    return BoardObject(
        object_id=obj.object_id,
        kind=obj.kind,
        author_uuid=obj.author_uuid,
        points=obj.points,
        data=dict(obj.data),
        vision_hint=hint,
        tool=obj.tool,
        verification=obj.verification,
        interaction=obj.interaction if interaction is _UNSET else interaction,
    )


def new_stroke(
    author_uuid: str,
    points: list,
    vision_hint: Optional[VisionHint] = None,
    tool: ToolKind = ToolKind.PEN,
) -> BoardObject:
    """Convenience constructor for a freehand stroke object."""
    return BoardObject(
        object_id=str(uuid.uuid4()),
        kind=ObjectKind.STROKE,
        author_uuid=author_uuid,
        points=tuple(Point(x, y) for x, y in points),
        vision_hint=vision_hint,
        tool=tool,
    )


def new_shape(
    author_uuid: str,
    tool: ToolKind,
    points: list,
) -> BoardObject:
    """Convenience constructor for a shape object authored by a shape tool.

    ``points`` defines the shape's defining geometry (e.g. two corners of a
    rectangle, two endpoints of a line). The tool must be a SHAPE tool.
    """
    if tool not in SHAPE_TOOLS:
        raise ValueError(f"{tool} is not a shape tool")
    return BoardObject(
        object_id=str(uuid.uuid4()),
        kind=ObjectKind.SHAPE,
        author_uuid=author_uuid,
        points=tuple(Point(x, y) for x, y in points),
        data={"shape": tool.value},
        tool=tool,
    )


def new_content_ref(
    author_uuid: str,
    kind: ObjectKind,
    content_ref: str,
    verification: ContentVerification,
) -> BoardObject:
    """Convenience constructor for a subject-aware generated content object.

    ``kind`` must be one of the generated-content kinds (3D model / simulation /
    animated explanation); ``content_ref`` is an opaque handle (no raw media).
    """
    if kind not in GENERATED_CONTENT_KINDS:
        raise ValueError(f"{kind} is not a subject-aware content kind")
    if not content_ref:
        raise ValueError("content_ref is required")
    return BoardObject(
        object_id=str(uuid.uuid4()),
        kind=kind,
        author_uuid=author_uuid,
        data={"content_ref": content_ref},
        verification=verification,
    )
