"""The translation interface: preserves subject terminology, handles
code-switching, and degrades to a content-preserving pass-through."""

from __future__ import annotations

from app.config import CommunicationSettings
from app.translation import TranslationInterface


def _ti() -> TranslationInterface:
    return TranslationInterface(settings=CommunicationSettings())  # no provider.


def test_passthrough_when_no_provider_returns_text_intact():
    ti = _ti()
    result = ti.render("Remember to revise photosynthesis.", target_lang="hi")
    assert result.status == "passthrough"
    assert result.rendered_text == "Remember to revise photosynthesis."  # never dropped.
    assert result.provider == "none_passthrough"


def test_protected_subject_terms_are_identified():
    ti = _ti()
    found = ti.find_protected_terms("The denominator of a quadratic equation matters.")
    assert "denominator" in found
    assert "quadratic equation" in found


def test_mask_and_restore_round_trip_preserves_terms_verbatim():
    ti = _ti()
    text = "Explain photosynthesis and the Pythagoras theorem."
    masked, mapping = ti.mask_protected_terms(text)
    # The masked text no longer contains the raw terms (they are protected spans).
    assert "photosynthesis" not in masked
    assert "Pythagoras theorem" not in masked
    # Restoration brings them back verbatim — meaning is never lost in translation.
    restored = ti.restore_protected_terms(masked, mapping)
    assert "photosynthesis" in restored
    assert "Pythagoras theorem" in restored


def test_code_switching_is_detected_and_preserved_as_spans():
    ti = _ti()
    text = "Beta aaj ka homework photosynthesis पर है"
    assert ti.is_code_switched(text) is True
    spans = ti.detect_spans(text)
    langs = {s.lang for s in spans if s.lang != "und"}
    assert "en" in langs and "hi" in langs


def test_single_language_text_is_not_flagged_as_code_switched():
    ti = _ti()
    assert ti.is_code_switched("Please revise the chapter tonight.") is False


def test_protected_terms_default_glossary_is_present():
    ti = _ti()
    assert "photosynthesis" in ti.protected_terms()


def test_render_for_reader_with_no_preference_passes_text_through_intact():
    # No preferred language -> honoured as "no translation wanted", never guessed.
    ti = _ti()
    result = ti.render_for_reader("Revise photosynthesis tonight.", preferred_lang=None)
    assert result.status == "passthrough"
    assert result.rendered_text == "Revise photosynthesis tonight."  # never dropped.
    assert result.target_lang == "und"
    assert "photosynthesis" in result.preserved_terms


def test_render_for_reader_blank_preference_is_treated_as_no_preference():
    ti = _ti()
    result = ti.render_for_reader("Hello.", preferred_lang="  ")
    assert result.status == "passthrough"
    assert result.target_lang == "und"


def test_render_for_reader_uses_the_readers_preferred_language_when_set():
    # With a preference but no provider, it degrades to passthrough toward that
    # language (never garbled, never sent off-box) — subject terms still kept.
    ti = _ti()
    result = ti.render_for_reader(
        "The denominator stays the same.", preferred_lang="hi"
    )
    assert result.target_lang == "hi"
    assert result.status == "passthrough"
    assert "denominator" in result.preserved_terms
