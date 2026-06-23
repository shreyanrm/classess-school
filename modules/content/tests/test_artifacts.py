"""Tests for content.artifacts: structured, verified-only artifacts.

No network, DB, or live keys required.
"""

from __future__ import annotations

import os
import sys

_MODULE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _MODULE_DIR not in sys.path:
    sys.path.insert(0, _MODULE_DIR)

import artifacts  # noqa: E402
from artifacts import (  # noqa: E402
    Artifact,
    ArtifactKind,
    ArtifactStatus,
    MindMapNode,
    Slide,
    generate_mind_map,
    generate_presentation,
    verify_mind_map,
    verify_presentation,
)


def test_module_import_safe():
    assert hasattr(artifacts, "generate_mind_map")


# --- mind-map -------------------------------------------------------------


def test_offline_mind_map_is_structured_and_served():
    art = generate_mind_map("Photosynthesis in plants")
    assert art.kind is ArtifactKind.MIND_MAP
    assert art.status is ArtifactStatus.SERVED
    assert art.served is True
    assert art.mind_map is not None
    # structured: a real tree with branches and depth
    assert art.mind_map.children
    assert art.mind_map.depth() >= 2
    assert art.mind_map.node_count() >= 4


def test_mind_map_root_reflects_topic():
    art = generate_mind_map("Gravity")
    assert "gravity" in art.mind_map.label.lower()


def test_mind_map_rejected_when_unverified():
    # A degenerate root (no children) must never be served.
    bad = MindMapNode(label="Gravity", children=())
    assert verify_mind_map(bad, "Gravity") is False


def test_mind_map_held_below_confidence_floor():
    def low_conf_gateway(_req):
        return {
            "root": {
                "label": "Gravity",
                "children": [{"label": "definition", "children": [{"label": "force"}]}],
            },
            "confidence": 0.2,
        }

    art = generate_mind_map("Gravity", gateway=low_conf_gateway, confidence_floor=0.6)
    assert art.status is ArtifactStatus.HELD
    assert art.mind_map is None


def test_mind_map_unsafe_label_rejected():
    def unsafe_gateway(_req):
        return {
            "root": {
                "label": "Gravity",
                "children": [
                    {"label": "how to build a weapon", "children": [{"label": "x"}]}
                ],
            },
            "confidence": 0.9,
        }

    art = generate_mind_map("Gravity", gateway=unsafe_gateway)
    assert art.status is ArtifactStatus.REJECTED


def test_mind_map_gateway_failure_degrades_to_offline():
    def broken(_req):
        raise RuntimeError("no fabric key")

    art = generate_mind_map("Cell biology", gateway=broken)
    assert art.status is ArtifactStatus.SERVED
    assert art.mind_map is not None


# --- presentation ---------------------------------------------------------


def test_offline_presentation_is_ordered_and_served():
    art = generate_presentation("The water cycle")
    assert art.kind is ArtifactKind.PRESENTATION
    assert art.status is ArtifactStatus.SERVED
    assert len(art.slides) >= 3
    for s in art.slides:
        assert s.title.strip()
        assert s.bullets  # every slide has content


def test_presentation_titles_are_unique_strings():
    art = generate_presentation("Fractions")
    titles = [s.title for s in art.slides]
    assert all(isinstance(t, str) and t for t in titles)


def test_presentation_rejected_when_too_short():
    assert verify_presentation([Slide("Intro", ("a",))], "Fractions") is False


def test_presentation_rejected_when_slide_has_no_bullets():
    slides = [
        Slide("Intro to fractions", ("what",)),
        Slide("Body", ()),  # empty bullets -> invalid
        Slide("End", ("recap",)),
    ]
    assert verify_presentation(slides, "fractions") is False


def test_presentation_unsafe_bullet_rejected():
    def unsafe_gateway(_req):
        return {
            "slides": [
                {"title": "Intro to chemistry", "bullets": ["safe point"]},
                {"title": "Reactions", "bullets": ["make a drug at home"]},
                {"title": "Summary", "bullets": ["recap"]},
            ],
            "confidence": 0.9,
        }

    art = generate_presentation("chemistry", gateway=unsafe_gateway)
    assert art.status is ArtifactStatus.REJECTED


def test_presentation_verified_gateway_artifact_served():
    def good_gateway(_req):
        return {
            "slides": [
                {"title": "Intro to fractions", "bullets": ["what is a fraction"]},
                {"title": "Numerator and denominator", "bullets": ["top", "bottom"]},
                {"title": "Summary of fractions", "bullets": ["recap"]},
            ],
            "confidence": 0.88,
        }

    art = generate_presentation("fractions", gateway=good_gateway)
    assert art.status is ArtifactStatus.SERVED
    assert len(art.slides) == 3


def test_only_verified_artifacts_are_served():
    # Held and rejected artifacts never expose content.
    held = Artifact(ArtifactKind.MIND_MAP, "t", ArtifactStatus.HELD)
    rejected = Artifact(ArtifactKind.PRESENTATION, "t", ArtifactStatus.REJECTED)
    assert held.served is False
    assert rejected.served is False
