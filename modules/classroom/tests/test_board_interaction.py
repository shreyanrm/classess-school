"""Board deepening, round 2: per-session interaction state for subject-aware
content (explore a 3D model / step an animation / set a simulation scenario) and
freeze-frame annotation management (erase / clear while frozen)."""

from __future__ import annotations

import pytest

from app import board, events
from app.board import (
    Board,
    BoardObject,
    ContentInteraction,
    ContentVerification,
    ObjectKind,
    new_content_ref,
    new_stroke,
)


def _uuid() -> str:
    return events.new_canonical_uuid()


def _commit_verified_model(b: Board) -> tuple[str, BoardObject]:
    v = ContentVerification(topic="cell structure", confidence=0.9, cross_checked=True)
    obj = new_content_ref(_uuid(), ObjectKind.MODEL_3D, "model://cell", v)
    shown, _ = b.stage_content(obj, b.pages[0].page_id)
    assert shown
    return b.pages[0].page_id, obj


# -- content interaction state ----------------------------------------------
def test_content_interaction_defaults_and_pure_update():
    base = ContentInteraction()
    assert base.viewpoint == "default"
    assert base.step == 0
    moved = base.at("cross_section", step=2, rotation_deg=90)
    assert moved.viewpoint == "cross_section"
    assert moved.step == 2
    assert moved.params["rotation_deg"] == 90
    # original is unchanged (pure)
    assert base.viewpoint == "default"
    assert "rotation_deg" not in base.params


def test_interaction_rejects_negative_step_and_raw_media():
    with pytest.raises(ValueError):
        ContentInteraction(step=-1)
    with pytest.raises(ValueError):
        ContentInteraction(params={"raw_media": b"x"})


def test_interaction_only_on_subject_aware_content():
    # plain text object cannot carry interaction state
    with pytest.raises(ValueError):
        BoardObject(
            object_id="t",
            kind=ObjectKind.TEXT,
            author_uuid=_uuid(),
            interaction=ContentInteraction(viewpoint="x"),
        )


def test_drive_content_moves_viewpoint_and_keeps_object_id():
    b = Board("s1")
    page_id, obj = _commit_verified_model(b)
    ev = b.drive_content(page_id, obj.object_id, ContentInteraction("cross_section", step=1))
    assert ev.kind is events.EventKind.BOARD_CONTENT_INTERACTED
    assert ev.payload["viewpoint"] == "cross_section"
    assert ev.payload["step"] == 1
    # same object id, now carrying interaction state, order preserved (single obj)
    placed = b.page(page_id).objects[0]
    assert placed.object_id == obj.object_id
    assert placed.interaction.viewpoint == "cross_section"


def test_drive_content_preserves_commit_order():
    b = Board("s1")
    page_id, model = _commit_verified_model(b)
    b.commit_object(page_id, new_stroke(_uuid(), [(0, 0), (1, 1)]))
    b.drive_content(page_id, model.object_id, ContentInteraction("side"))
    objs = b.page(page_id).objects
    assert objs[0].object_id == model.object_id  # model still first
    assert objs[0].interaction.viewpoint == "side"


def test_drive_content_refuses_non_content_object():
    b = Board("s1")
    page_id = b.pages[0].page_id
    stroke = new_stroke(_uuid(), [(0, 0), (1, 1)])
    b.commit_object(page_id, stroke)
    with pytest.raises(ValueError):
        b.drive_content(page_id, stroke.object_id, ContentInteraction("x"))


def test_drive_content_unknown_object_raises():
    b = Board("s1")
    with pytest.raises(KeyError):
        b.drive_content(b.pages[0].page_id, "nope", ContentInteraction("x"))


# -- freeze-frame annotation management -------------------------------------
def test_erase_while_frozen_removes_annotation_not_live():
    b = Board("s1")
    page_id = b.pages[0].page_id
    live = new_stroke(_uuid(), [(0, 0), (1, 1)])
    b.commit_object(page_id, live)

    b.freeze_frame(page_id, _uuid())
    ann = new_stroke(_uuid(), [(2, 2), (3, 3)])
    b.commit_object(page_id, ann)
    assert len(b.frozen_frame.annotations) == 1

    b.erase_object(page_id, ann.object_id)
    assert len(b.frozen_frame.annotations) == 0
    # the live object is untouched
    assert len(b.page(page_id).objects) == 1
    assert b.page(page_id).objects[0].object_id == live.object_id


def test_clear_annotations_wipes_markup_keeps_live_page():
    b = Board("s1")
    page_id = b.pages[0].page_id
    b.commit_object(page_id, new_stroke(_uuid(), [(0, 0), (1, 1)]))
    b.freeze_frame(page_id, _uuid())
    b.commit_object(page_id, new_stroke(_uuid(), [(2, 2), (3, 3)]))
    b.commit_object(page_id, new_stroke(_uuid(), [(4, 4), (5, 5)]))
    assert len(b.frozen_frame.annotations) == 2

    b.clear_annotations()
    assert len(b.frozen_frame.annotations) == 0
    # base frame and live page preserved
    assert len(b.frozen_frame.base_objects) == 1
    b.resume_live(_uuid())
    assert len(b.page(page_id).objects) == 1


def test_clear_annotations_is_noop_when_live():
    b = Board("s1")
    page_id = b.pages[0].page_id
    b.commit_object(page_id, new_stroke(_uuid(), [(0, 0), (1, 1)]))
    b.clear_annotations()  # not frozen -> no effect, no error
    assert len(b.page(page_id).objects) == 1
