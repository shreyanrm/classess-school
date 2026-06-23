"""Board state ops: pages, object commit, immutability, vision-assist gate."""

from __future__ import annotations

import pytest

from app import board, events
from app.board import Board, BoardObject, ObjectKind, VisionHint, new_stroke


def _uuid() -> str:
    return events.new_canonical_uuid()


def test_board_opens_with_one_page():
    b = Board("s1")
    assert len(b.pages) == 1
    assert b.object_count() == 0


def test_add_page_increments_index():
    b = Board("s1")
    p = b.add_page()
    assert p.index == 1
    assert len(b.pages) == 2


def test_commit_stroke_appends_object_and_emits_event():
    b = Board("s1")
    page = b.pages[0]
    author = _uuid()
    stroke = new_stroke(author, [(0, 0), (1, 1), (2, 2)])
    ev = b.commit_object(page.page_id, stroke)
    assert b.object_count() == 1
    assert ev.kind == events.EventKind.BOARD_OBJECT_COMMITTED
    assert ev.subject_uuid == author


def test_infinite_canvas_allows_arbitrary_coordinates():
    b = Board("s1")
    stroke = new_stroke(_uuid(), [(-1e9, 1e9), (123456.7, -987654.3)])
    ev = b.commit_object(b.pages[0].page_id, stroke)
    assert ev is not None


def test_pages_are_immutable_values():
    b = Board("s1")
    page = b.pages[0]
    with pytest.raises(Exception):
        page.index = 99  # frozen


def test_vision_hint_below_gate_is_dropped():
    b = Board("s1")
    weak = VisionHint(label="triangle", confidence=0.40)
    obj = BoardObject(
        object_id="o1",
        kind=ObjectKind.SHAPE,
        author_uuid=_uuid(),
        data={"shape": "freeform"},
        vision_hint=weak,
    )
    ev = b.commit_object(b.pages[0].page_id, obj)
    # hint dropped -> not present in event payload (generate-and-verify)
    assert "vision_hint" not in ev.payload


def test_vision_hint_above_gate_is_kept_and_assistive():
    b = Board("s1")
    strong = VisionHint(label="triangle", confidence=0.92)
    obj = BoardObject(
        object_id="o2",
        kind=ObjectKind.SHAPE,
        author_uuid=_uuid(),
        data={"shape": "freeform"},
        vision_hint=strong,
    )
    ev = b.commit_object(b.pages[0].page_id, obj)
    assert ev.payload["vision_hint"]["assistive"] is True
    assert ev.payload["vision_hint"]["label"] == "triangle"


def test_vision_never_grades_from_a_face():
    with pytest.raises(ValueError):
        VisionHint(label="bored", confidence=0.99, source_is_face=True)


def test_board_object_refuses_raw_image_bytes():
    with pytest.raises(ValueError):
        BoardObject(
            object_id="o3",
            kind=ObjectKind.IMAGE_REF,
            author_uuid=_uuid(),
            data={"raw_image": b"..."},
        )


def test_author_must_be_opaque_uuid():
    with pytest.raises(ValueError):
        new_stroke("Teacher Bob", [(0, 0), (1, 1)])


def test_erase_object_removes_it():
    b = Board("s1")
    stroke = new_stroke(_uuid(), [(0, 0), (1, 1)])
    b.commit_object(b.pages[0].page_id, stroke)
    b.erase_object(b.pages[0].page_id, stroke.object_id)
    assert b.object_count() == 0
