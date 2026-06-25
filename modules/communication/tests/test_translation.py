"""The translation interface: REAL translation through the gateway to the model
router when configured, preserving subject terminology + code-switching, and
degrading to a content-preserving pass-through when not."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.config import CommunicationSettings
from app.translation import (
    GATEWAY_ROUTE_PATH,
    GATEWAY_TOKEN_ENV_VAR,
    TranslationInterface,
)


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


# ---------------------------------------------------------------------------
# The LIVE translation path (through the gateway to the model router).
# Exercised entirely OFFLINE via an injected transport.
# ---------------------------------------------------------------------------

def _wired_settings() -> CommunicationSettings:
    return CommunicationSettings(
        gateway_url="https://gateway.internal",
        translation_url="https://provider/translate",  # marks translation configured
    )


@dataclass
class FakeTransport:
    """Echoes the masked text back as the 'translation' (the placeholders survive,
    so restoration brings the protected terms back verbatim). Records the request
    so the test can assert how egress happened."""

    reply_key: str = "rendered_text"
    seen_url: str | None = None
    seen_headers: dict | None = None
    seen_body: dict | None = None

    def post_json(self, *, url, headers, json_body, timeout):
        self.seen_url = url
        self.seen_headers = dict(headers)
        self.seen_body = dict(json_body)
        # Simulate translation by wrapping the masked text; placeholders intact.
        return {self.reply_key: f"[hi] {json_body['text']}"}


@dataclass
class ExplodingTransport:
    def post_json(self, *, url, headers, json_body, timeout):
        raise RuntimeError("gateway unreachable")


def _ti_wired(transport, monkeypatch) -> TranslationInterface:
    monkeypatch.setenv(GATEWAY_TOKEN_ENV_VAR, "bearer-NOLEAK")
    return TranslationInterface(settings=_wired_settings(), transport=transport)


def test_live_translation_is_taken_when_configured(monkeypatch):
    transport = FakeTransport()
    ti = _ti_wired(transport, monkeypatch)
    result = ti.render("Explain photosynthesis clearly.", target_lang="hi")
    # The REAL path was taken: status translated, provider is the gateway route.
    assert result.status == "translated"
    assert result.provider == "gateway_translation"
    assert result.rendered_text.startswith("[hi] ")
    # Egress passed the gateway route entrypoint, asserting the purpose, with the
    # bearer ONLY in the Authorization header (never in the body).
    assert transport.seen_url.endswith(GATEWAY_ROUTE_PATH)
    assert transport.seen_headers["Authorization"] == "Bearer bearer-NOLEAK"
    assert transport.seen_headers["X-Consent-Purpose"] == "communication"
    assert "bearer-NOLEAK" not in str(transport.seen_body)


def test_live_translation_preserves_subject_terms_verbatim(monkeypatch):
    transport = FakeTransport()
    ti = _ti_wired(transport, monkeypatch)
    result = ti.render("Revise photosynthesis and the Pythagoras theorem.", target_lang="hi")
    # The protected terms were MASKED before egress (never sent raw)...
    assert "photosynthesis" not in transport.seen_body["text"]
    assert "Pythagoras theorem" not in transport.seen_body["text"]
    # ...and restored verbatim in the rendered output (meaning never lost).
    assert "photosynthesis" in result.rendered_text
    assert "Pythagoras theorem" in result.rendered_text
    assert "photosynthesis" in result.preserved_terms


def test_live_translation_degrades_to_passthrough_on_transport_error(monkeypatch):
    ti = _ti_wired(ExplodingTransport(), monkeypatch)
    result = ti.render("Revise photosynthesis tonight.", target_lang="hi")
    # A provider failure NEVER drops or garbles content — intact passthrough.
    assert result.status == "passthrough"
    assert result.rendered_text == "Revise photosynthesis tonight."
    assert "photosynthesis" in result.preserved_terms


def test_live_translation_degrades_without_token(monkeypatch):
    monkeypatch.delenv(GATEWAY_TOKEN_ENV_VAR, raising=False)
    ti = TranslationInterface(settings=_wired_settings(), transport=FakeTransport())
    result = ti.render("Hello there.", target_lang="hi")
    # Configured provider but no credential => degrade, never fabricate.
    assert result.status == "passthrough"
    assert result.rendered_text == "Hello there."


def test_live_translation_degrades_on_unrecognised_reply_shape(monkeypatch):
    transport = FakeTransport(reply_key="something_else")  # no known text key
    ti = _ti_wired(transport, monkeypatch)
    result = ti.render("Revise tonight.", target_lang="hi")
    assert result.status == "passthrough"
    assert result.rendered_text == "Revise tonight."


def test_render_for_reader_uses_live_path_when_wired(monkeypatch):
    transport = FakeTransport()
    ti = _ti_wired(transport, monkeypatch)
    result = ti.render_for_reader("Revise the denominator.", preferred_lang="hi")
    assert result.status == "translated"
    assert result.target_lang == "hi"
    assert "denominator" in result.rendered_text
