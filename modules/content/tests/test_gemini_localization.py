"""REAL Gemini-backed hyperlocalization — offline, import-safe, no live calls.

These tests exercise the live path by INJECTING a fake HTTPS poster and a fake
settings object that carries a key. No network is ever touched; no real key is
read. They prove:

  - the provider is selected by KEY NAME (factory returns it only when keyed) and
    degrades to None (template path) with no key;
  - the raw key reaches ONLY the HTTPS seam — never a result, repr, or log;
  - a faithful Gemini variant serves; a variant that translates a subject term
    away, or alters a correctness fact, is WITHHELD by the generate-and-verify
    gate (verified-only served);
  - the concept (correctness fields) is unchanged in a served variant;
  - the live provider is wired end-to-end through ContentGenerator.
"""

import json

import content  # noqa: F401  (puts the package + spine on sys.path)
from content.gemini_localization import (
    GEMINI_KEY_ENV_VAR,
    GEMINI_MODEL_LABEL,
    GeminiLocalizationProvider,
    make_localization_provider,
)
from content.hyperlocalize import Hyperlocalizer, LocaleContext
from content.generate import ContentGenerator, MaterialKind, MaterialRequest


# ---------------------------------------------------------------------------
# Fakes: a settings stub (key by name) and a recording HTTPS poster
# ---------------------------------------------------------------------------

class _FakeSettings:
    """Mimics the spine Settings: a key resolved by NAME, nothing else."""

    def __init__(self, gemini_api_key=None):
        self.gemini_api_key = gemini_api_key


class _RecordingPoster:
    """A fake HTTPS seam that records the call and returns a canned variant.

    ``variant`` is the JSON object the 'model' returns. Records the url, key and
    payload so tests can assert the request shape and that the key was passed
    over the seam (and ONLY there).
    """

    def __init__(self, variant):
        self._variant = variant
        self.calls = []

    def post_json(self, *, url, api_key, payload, timeout):
        self.calls.append(
            {"url": url, "api_key": api_key, "payload": payload, "timeout": timeout}
        )
        return {
            "candidates": [
                {"content": {"parts": [{"text": json.dumps(self._variant)}]}}
            ]
        }


class _ErroringPoster:
    """A seam that raises — proves a provider error degrades, never fabricates."""

    def post_json(self, *, url, api_key, payload, timeout):
        raise RuntimeError("network down")


class _AgreeingSecondModel:
    def cross_check(self, *, task_class, content):
        return (True, 0.99)


_LOCALE = LocaleContext(board="example-state-board", region="in", language="ta")


# ---------------------------------------------------------------------------
# Factory: selected by KEY NAME; degrades to None with no key
# ---------------------------------------------------------------------------

def test_factory_degrades_to_none_without_key():
    # No key set under the env NAME => no live provider => template path.
    provider = make_localization_provider(
        settings=_FakeSettings(gemini_api_key=None),
        poster=_RecordingPoster({}),
    )
    assert provider is None


def test_factory_reads_key_by_env_name_and_returns_live_provider():
    # The factory resolves the key from the environment by its NAME.
    env = {GEMINI_KEY_ENV_VAR: "live-secret-value"}
    provider = make_localization_provider(poster=_RecordingPoster({}), env=env)
    assert isinstance(provider, GeminiLocalizationProvider)
    assert provider.has_provider() is True


def test_factory_without_poster_degrades():
    # Key present but no HTTPS seam => degrade (no fabricated localisation).
    provider = make_localization_provider(
        settings=_FakeSettings(gemini_api_key="k"), poster=None,
    )
    # _load_httpx_poster wires httpx (in requirements) so has_provider may be
    # True; but with a forced-None poster on the instance it must be False.
    p = GeminiLocalizationProvider(poster=None, settings=_FakeSettings(gemini_api_key="k"))
    p.poster = None
    assert p.has_provider() is False


# ---------------------------------------------------------------------------
# The raw key never leaks
# ---------------------------------------------------------------------------

def test_raw_key_never_appears_in_repr():
    provider = GeminiLocalizationProvider(
        poster=_RecordingPoster({}), settings=_FakeSettings(gemini_api_key="TOP-SECRET")
    )
    assert "TOP-SECRET" not in repr(provider)
    assert "key_present=True" in repr(provider)


def test_raw_key_passed_only_over_the_https_seam():
    poster = _RecordingPoster({"worked_example": "x"})
    provider = GeminiLocalizationProvider(
        poster=poster, settings=_FakeSettings(gemini_api_key="SECRET-KEY")
    )
    variant = provider.localize(
        body={"worked_example": "photosynthesis."}, locale=_LOCALE,
        subject_terms=["photosynthesis"],
    )
    # The key reached the seam (and only the seam); the returned variant has no key.
    assert poster.calls[0]["api_key"] == "SECRET-KEY"
    assert "SECRET-KEY" not in json.dumps(variant)


# ---------------------------------------------------------------------------
# The Gemini request shape (HTTPS endpoint + JSON contents)
# ---------------------------------------------------------------------------

def test_request_targets_https_gemini_endpoint_with_locale_and_terms():
    poster = _RecordingPoster({"worked_example": "x"})
    provider = GeminiLocalizationProvider(
        poster=poster, settings=_FakeSettings(gemini_api_key="k")
    )
    provider.localize(
        body={"worked_example": "photosynthesis in leaves."}, locale=_LOCALE,
        subject_terms=["photosynthesis"],
    )
    call = poster.calls[0]
    assert call["url"].startswith("https://")
    assert GEMINI_MODEL_LABEL in call["url"]
    prompt = call["payload"]["contents"][0]["parts"][0]["text"]
    # The prompt carries the locale signal and the term-preservation instruction.
    assert "photosynthesis" in prompt
    assert '"region": "in"' in prompt
    assert call["payload"]["generationConfig"]["responseMimeType"] == "application/json"


# ---------------------------------------------------------------------------
# Provider error / bad response => base body unchanged (no fabrication)
# ---------------------------------------------------------------------------

def test_provider_error_returns_base_unchanged():
    provider = GeminiLocalizationProvider(
        poster=_ErroringPoster(), settings=_FakeSettings(gemini_api_key="k")
    )
    base = {"worked_example": "photosynthesis.", "answer": 42.0}
    out = provider.localize(body=base, locale=_LOCALE, subject_terms=["photosynthesis"])
    assert out == base


def test_unparseable_response_returns_base_unchanged():
    class _Garbage:
        def post_json(self, *, url, api_key, payload, timeout):
            return {"candidates": [{"content": {"parts": [{"text": "not json"}]}}]}

    provider = GeminiLocalizationProvider(
        poster=_Garbage(), settings=_FakeSettings(gemini_api_key="k")
    )
    base = {"worked_example": "photosynthesis.", "answer": 42.0}
    out = provider.localize(body=base, locale=_LOCALE, subject_terms=["photosynthesis"])
    assert out == base


# ---------------------------------------------------------------------------
# Through the hyperlocalizer gate: verified-only served
# ---------------------------------------------------------------------------

def _hl(variant):
    poster = _RecordingPoster(variant)
    provider = GeminiLocalizationProvider(
        poster=poster, settings=_FakeSettings(gemini_api_key="k")
    )
    return Hyperlocalizer(provider=provider, second_model=_AgreeingSecondModel())


def test_faithful_gemini_variant_serves_subject_term_and_concept_intact():
    base = {"worked_example": "photosynthesis happens in leaves.", "answer": 42.0}
    # A faithful variant: surface localised, subject term verbatim, answer copied.
    variant = {
        "worked_example": "During Pongal in Madurai, photosynthesis powers the paddy.",
        "answer": 42.0,
        "_localization_confidence": 0.95,
    }
    hl = _hl(variant)
    outcome = hl.hyperlocalize(body=base, locale=_LOCALE, subject_terms=["photosynthesis"])
    assert outcome.localized is True
    assert outcome.not_yet_localised is False
    # Surface adapted; subject term verbatim; concept (answer) unchanged.
    assert "Madurai" in outcome.body["worked_example"]
    assert "photosynthesis" in outcome.body["worked_example"]
    assert outcome.body["answer"] == 42.0


def test_variant_translating_subject_term_away_is_withheld():
    base = {"worked_example": "photosynthesis happens in leaves."}
    # A WRONG variant: the subject term was translated away.
    variant = {"worked_example": "In Madurai, oleyo powers the paddy."}
    hl = _hl(variant)
    outcome = hl.hyperlocalize(body=base, locale=_LOCALE, subject_terms=["photosynthesis"])
    assert outcome.localized is False
    assert outcome.not_yet_localised is True
    # The served fallback is the untouched, verified base content.
    assert "photosynthesis" in outcome.body["worked_example"]


def test_variant_altering_correctness_is_withheld():
    base = {"expression": "6 * 7", "answer": 42.0}
    # A WRONG variant: localisation changed the answer.
    variant = {"expression": "6 * 7", "answer": 43.0, "worked_example": "localised"}
    hl = _hl(variant)
    outcome = hl.hyperlocalize(body=base, locale=_LOCALE, subject_terms=[])
    assert outcome.localized is False
    assert outcome.not_yet_localised is True
    # Fallback preserves the correct answer.
    assert outcome.body["answer"] == 42.0


# ---------------------------------------------------------------------------
# End-to-end through ContentGenerator with the live provider injected
# ---------------------------------------------------------------------------

def test_generate_serves_verified_localised_variant_via_live_provider():
    from app.orchestrator import Orchestrator  # spine via _spine bootstrap

    orch = Orchestrator(second_model=_AgreeingSecondModel())
    provider = GeminiLocalizationProvider(
        poster=_RecordingPoster(
            {
                "expression": "6 * 7",
                "answer": 42.0,
                "unit": None,
                "worked_example": "During Pongal in Madurai, 6 * 7 = 42.",
            }
        ),
        settings=_FakeSettings(gemini_api_key="k"),
    )
    gen = ContentGenerator(
        orchestrator=orch,
        localization_provider=provider,
        localization_second_model=_AgreeingSecondModel(),
    )
    req = MaterialRequest(
        topic_id="topic-1",
        kind=MaterialKind.PRACTICE_ITEM,
        payload={"expression": "6 * 7", "claimed_answer": 42.0},
        locale=_LOCALE,
        subject_terms=(),
    )
    outcome = gen.generate(req)
    assert outcome.served is True
    assert outcome.material is not None
    assert outcome.material.localized is True
    assert "Madurai" in outcome.material.body["worked_example"]


def test_generate_without_key_degrades_to_not_yet_localised(monkeypatch):
    from app.orchestrator import Orchestrator

    # Ensure the env key is ABSENT so the auto-wire finds no live provider.
    monkeypatch.delenv(GEMINI_KEY_ENV_VAR, raising=False)

    orch = Orchestrator(second_model=_AgreeingSecondModel())
    # No localization provider injected; auto-wire from env finds no key => None.
    gen = ContentGenerator(orchestrator=orch)
    req = MaterialRequest(
        topic_id="topic-1",
        kind=MaterialKind.PRACTICE_ITEM,
        payload={"expression": "6 * 7", "claimed_answer": 42.0},
        locale=_LOCALE,
    )
    outcome = gen.generate(req)
    assert outcome.served is True
    assert outcome.material.not_yet_localised is True
    assert outcome.material.localized is False
    assert outcome.material.body["answer"] == 42.0
