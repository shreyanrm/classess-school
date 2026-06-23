"""Board deepening: themes, tool model, document sharing, freeze-frame,
subject-aware content refs with per-session generate-and-verify."""

from __future__ import annotations

import pytest

from app import board, events
from app.board import (
    Board,
    BoardObject,
    BoardTheme,
    ContentVerification,
    ObjectKind,
    ToolKind,
    new_content_ref,
    new_shape,
    new_stroke,
)


def _uuid() -> str:
    return events.new_canonical_uuid()


# -- themes -----------------------------------------------------------------
def test_board_default_theme_and_switch():
    b = Board("s1")
    assert b.theme is BoardTheme.LIGHT
    ev = b.set_theme(BoardTheme.CHALK, _uuid())
    assert b.theme is BoardTheme.CHALK
    assert ev.kind is events.EventKind.BOARD_THEME_CHANGED
    assert ev.payload["theme"] == "chalk"


def test_set_theme_requires_opaque_uuid():
    b = Board("s1")
    with pytest.raises(ValueError):
        b.set_theme(BoardTheme.DARK, "Teacher Bob")


def test_board_can_open_with_a_chosen_theme():
    b = Board("s1", theme=BoardTheme.GRID)
    assert b.theme is BoardTheme.GRID


# -- tool model -------------------------------------------------------------
def test_default_tool_is_pen_and_selectable():
    b = Board("s1")
    assert b.active_tool is ToolKind.PEN
    assert b.select_tool(ToolKind.HIGHLIGHTER) is ToolKind.HIGHLIGHTER
    assert b.active_tool is ToolKind.HIGHLIGHTER


def test_new_shape_records_its_tool_and_kind():
    obj = new_shape(_uuid(), ToolKind.RECTANGLE, [(0, 0), (4, 3)])
    assert obj.kind is ObjectKind.SHAPE
    assert obj.tool is ToolKind.RECTANGLE
    assert obj.data["shape"] == "rectangle"


def test_new_shape_rejects_non_shape_tool():
    with pytest.raises(ValueError):
        new_shape(_uuid(), ToolKind.ERASER, [(0, 0)])


def test_commit_carries_tool_in_payload():
    b = Board("s1")
    stroke = new_stroke(_uuid(), [(0, 0), (1, 1)], tool=ToolKind.HIGHLIGHTER)
    ev = b.commit_object(b.pages[0].page_id, stroke)
    assert ev.payload["tool"] == "highlighter"


# -- document sharing -------------------------------------------------------
def test_share_document_places_typed_ref_no_raw_bytes():
    b = Board("s1")
    obj, ev = b.share_document(
        b.pages[0].page_id, _uuid(), "doc://opaque-123", title="Worksheet"
    )
    assert obj.kind is ObjectKind.DOCUMENT_REF
    assert obj.data["document_ref"] == "doc://opaque-123"
    assert ev.kind is events.EventKind.BOARD_DOCUMENT_SHARED
    assert b.object_count() == 1


def test_board_object_refuses_raw_media_bytes():
    with pytest.raises(ValueError):
        BoardObject(
            object_id="x",
            kind=ObjectKind.DOCUMENT_REF,
            author_uuid=_uuid(),
            data={"raw_media": b"..."},
        )


# -- freeze-frame annotate mode --------------------------------------------
def test_freeze_then_annotate_does_not_mutate_live_page():
    b = Board("s1")
    page_id = b.pages[0].page_id
    b.commit_object(page_id, new_stroke(_uuid(), [(0, 0), (1, 1)]))
    assert b.object_count() == 1

    ev = b.freeze_frame(page_id, _uuid())
    assert ev.kind is events.EventKind.BOARD_FRAME_FROZEN
    assert b.is_frozen

    # annotate on the frozen frame
    b.commit_object(page_id, new_stroke(_uuid(), [(2, 2), (3, 3)]))
    # live page is untouched (still one object)
    assert len(b.page(page_id).objects) == 1
    assert len(b.frozen_frame.annotations) == 1


def test_resume_discards_annotations_by_default():
    b = Board("s1")
    page_id = b.pages[0].page_id
    b.freeze_frame(page_id, _uuid())
    b.commit_object(page_id, new_stroke(_uuid(), [(0, 0), (1, 1)]))
    ev = b.resume_live(_uuid())
    assert not b.is_frozen
    assert ev.payload["annotations_kept"] == 0
    assert len(b.page(page_id).objects) == 0


def test_resume_can_keep_annotations_as_record():
    b = Board("s1")
    page_id = b.pages[0].page_id
    b.freeze_frame(page_id, _uuid())
    b.commit_object(page_id, new_stroke(_uuid(), [(0, 0), (1, 1)]))
    ev = b.resume_live(_uuid(), keep_annotations=True)
    assert ev.payload["annotations_kept"] == 1
    assert len(b.page(page_id).objects) == 1


def test_cannot_double_freeze_or_resume_when_live():
    b = Board("s1")
    page_id = b.pages[0].page_id
    with pytest.raises(RuntimeError):
        b.resume_live(_uuid())  # not frozen
    b.freeze_frame(page_id, _uuid())
    with pytest.raises(RuntimeError):
        b.freeze_frame(page_id, _uuid())  # already frozen


def test_freeze_commit_event_marks_frozen():
    b = Board("s1")
    page_id = b.pages[0].page_id
    b.freeze_frame(page_id, _uuid())
    ev = b.commit_object(page_id, new_stroke(_uuid(), [(0, 0), (1, 1)]))
    assert ev.payload["frozen"] is True


# -- subject-aware generated content + generate-and-verify ------------------
def test_generated_content_requires_verification_metadata():
    with pytest.raises(ValueError):
        BoardObject(
            object_id="m1",
            kind=ObjectKind.MODEL_3D,
            author_uuid=_uuid(),
            data={"content_ref": "model://x"},
        )


def test_verified_content_is_committed_and_shown():
    b = Board("s1")
    v = ContentVerification(topic="cell structure", confidence=0.9, cross_checked=True)
    obj = new_content_ref(_uuid(), ObjectKind.MODEL_3D, "model://cell", v)
    shown, ev = b.stage_content(obj, b.pages[0].page_id)
    assert shown is True
    assert ev.kind is events.EventKind.BOARD_CONTENT_VERIFIED
    assert ev.payload["verified"] is True
    assert b.object_count() == 1


def test_unverified_content_is_deferred_not_shown():
    b = Board("s1")
    v = ContentVerification(topic="cell structure", confidence=0.4)
    obj = new_content_ref(_uuid(), ObjectKind.SIMULATION, "sim://x", v)
    shown, ev = b.stage_content(obj, b.pages[0].page_id)
    assert shown is False
    assert ev.payload["verified"] is False
    assert b.object_count() == 0  # nothing unverified placed on the board


def test_committing_unverified_content_directly_is_refused():
    b = Board("s1")
    v = ContentVerification(topic="t", confidence=0.3)
    obj = new_content_ref(_uuid(), ObjectKind.ANIMATED_EXPLANATION, "anim://x", v)
    with pytest.raises(ValueError):
        b.commit_object(b.pages[0].page_id, obj)


def test_content_ref_kind_must_be_subject_aware():
    v = ContentVerification(topic="t", confidence=0.9)
    with pytest.raises(ValueError):
        new_content_ref(_uuid(), ObjectKind.TEXT, "x", v)


def test_content_verification_validates_topic_and_confidence():
    with pytest.raises(ValueError):
        ContentVerification(topic="", confidence=0.9)
    with pytest.raises(ValueError):
        ContentVerification(topic="t", confidence=1.5)
