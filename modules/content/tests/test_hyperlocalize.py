"""Hyperlocalization: relevance not translation, verified before served.

Covers the non-negotiables:
  - subject terms are preserved VERBATIM (photosynthesis stays photosynthesis);
  - the concept and its correctness never change;
  - the LocaleContext drives the surface adaptation;
  - it degrades gracefully with no provider (base content, not-yet-localised);
  - board is a FIELD on the locale, never a lock-in enum;
  - nothing unverified is served — a variant that drops a subject term or
    alters a correctness fact is WITHHELD by the gate.
"""

import content  # noqa: F401  (puts the package + spine on sys.path)
from content.hyperlocalize import (
    Hyperlocalizer,
    LocaleContext,
    concept_unchanged,
    subject_terms_preserved,
)
from content.generate import (
    ContentGenerator,
    MaterialKind,
    MaterialRequest,
)


# ---------------------------------------------------------------------------
# Test localisation providers
# ---------------------------------------------------------------------------

class _RelevanceProvider:
    """A faithful localisation: adapts the SURFACE (examples, places, units,
    festival-aware calendar) into the reader's language, preserving subject
    terms verbatim and never touching correctness-bearing fields."""

    def localize(self, *, body, locale, subject_terms):
        out = dict(body)
        # Relevance, not translation: a worked example reframed for this locale,
        # in the reader's language, with the subject term kept verbatim.
        term = subject_terms[0] if subject_terms else "the concept"
        place = {"in": "Madurai", "ke": "Mombasa"}.get(locale.region or "", "the town")
        festival = {"in": "Pongal", "ke": "Idd"}.get(locale.region or "", "the harvest festival")
        out["worked_example"] = (
            f"During {festival} in {place}, observe {term} in the local fields."
        )
        return out


class _Translator:
    """A WRONG localisation that translates the subject term away (it should be
    preserved verbatim). The gate must withhold this."""

    def localize(self, *, body, locale, subject_terms):
        out = dict(body)
        text = body.get("worked_example", "")
        for term in subject_terms:
            text = text.replace(term, " olelizicovi")  # translated the subject term
        out["worked_example"] = text
        return out


class _ConceptBender:
    """A WRONG localisation that alters a correctness-bearing fact (the answer)."""

    def localize(self, *, body, locale, subject_terms):
        out = dict(body)
        if "answer" in out:
            out["answer"] = float(out["answer"]) + 1.0  # changed correctness
        out["worked_example"] = "localised surface text"
        return out


class _AgreeingSecondModel:
    def cross_check(self, *, task_class, content):
        return (True, 0.99)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def test_subject_terms_preserved_verbatim_helper():
    base = {"worked_example": "Photosynthesis converts light to energy."}
    good = {"worked_example": "In Madurai, Photosynthesis powers the paddy."}
    bad = {"worked_example": "In Madurai, dyutisamayoga powers the paddy."}
    # A term present verbatim in the base must survive verbatim in the variant.
    ok, viol = subject_terms_preserved(
        subject_terms=["Photosynthesis"], base_body=base, localized_body=good
    )
    assert ok is True and viol == []
    # Translating the subject term away is a violation.
    ok2, viol2 = subject_terms_preserved(
        subject_terms=["Photosynthesis"], base_body=base, localized_body=bad
    )
    assert ok2 is False
    assert "Photosynthesis" in viol2
    # A term NOT in the base is not something to preserve (no false violation).
    ok3, viol3 = subject_terms_preserved(
        subject_terms=["mitosis"], base_body=base, localized_body=bad
    )
    assert ok3 is True and viol3 == []


def test_concept_unchanged_helper():
    base = {"expression": "6 * 7", "answer": 42.0}
    same = {"expression": "6 * 7", "answer": 42.0, "worked_example": "localised"}
    changed = {"expression": "6 * 7", "answer": 43.0}
    assert concept_unchanged(base_body=base, localized_body=same) == (True, [])
    ok, viol = concept_unchanged(base_body=base, localized_body=changed)
    assert ok is False and "answer" in viol


# ---------------------------------------------------------------------------
# Hyperlocalizer — graceful degradation
# ---------------------------------------------------------------------------

def test_degrades_without_provider_to_not_yet_localised():
    hl = Hyperlocalizer()  # no provider
    base = {"worked_example": "Photosynthesis in the field.", "answer": 42.0}
    locale = LocaleContext(board="example-state-board", language="ta", region="in")
    outcome = hl.hyperlocalize(body=base, locale=locale, subject_terms=["Photosynthesis"])
    assert outcome.localized is False
    assert outcome.not_yet_localised is True
    assert outcome.body["hyperlocalization"]["not_yet_localised"] is True
    # The base content survives unchanged underneath the marker.
    assert outcome.body["worked_example"] == base["worked_example"]
    assert outcome.body["answer"] == 42.0


def test_unspecified_locale_is_not_localised():
    hl = Hyperlocalizer(provider=_RelevanceProvider(), second_model=_AgreeingSecondModel())
    outcome = hl.hyperlocalize(
        body={"worked_example": "Photosynthesis."},
        locale=LocaleContext(),  # nothing set
        subject_terms=["Photosynthesis"],
    )
    assert outcome.localized is False
    assert outcome.not_yet_localised is True


# ---------------------------------------------------------------------------
# Hyperlocalizer — verified localisation
# ---------------------------------------------------------------------------

def test_locale_drives_surface_adaptation_and_serves_when_verified():
    hl = Hyperlocalizer(
        provider=_RelevanceProvider(), second_model=_AgreeingSecondModel()
    )
    base = {"worked_example": "photosynthesis happens in leaves.", "answer": 42.0}
    locale = LocaleContext(
        board="example-state-board", language="ta", region="in", calendar="example-academic"
    )
    outcome = hl.hyperlocalize(body=base, locale=locale, subject_terms=["photosynthesis"])
    assert outcome.localized is True
    assert outcome.not_yet_localised is False
    # Surface adapted to the locale: place + festival from the region.
    assert "Madurai" in outcome.body["worked_example"]
    assert "Pongal" in outcome.body["worked_example"]
    # Subject term preserved verbatim.
    assert "photosynthesis" in outcome.body["worked_example"]
    # Concept correctness unchanged.
    assert outcome.body["answer"] == 42.0
    assert outcome.body["hyperlocalization"]["localized"] is True
    assert outcome.body["hyperlocalization"]["locale"]["region"] == "in"


def test_different_locale_yields_different_surface_same_concept():
    hl = Hyperlocalizer(
        provider=_RelevanceProvider(), second_model=_AgreeingSecondModel()
    )
    base = {"worked_example": "photosynthesis happens in leaves.", "answer": 42.0}
    in_outcome = hl.hyperlocalize(
        body=base, locale=LocaleContext(region="in", language="ta"),
        subject_terms=["photosynthesis"],
    )
    ke_outcome = hl.hyperlocalize(
        body=base, locale=LocaleContext(region="ke", language="sw"),
        subject_terms=["photosynthesis"],
    )
    # Same concept term, same correctness; DIFFERENT surface per locale.
    assert in_outcome.body["worked_example"] != ke_outcome.body["worked_example"]
    assert "Mombasa" in ke_outcome.body["worked_example"]
    assert in_outcome.body["answer"] == ke_outcome.body["answer"] == 42.0
    assert "photosynthesis" in ke_outcome.body["worked_example"]


def test_translating_subject_term_away_is_withheld():
    hl = Hyperlocalizer(provider=_Translator(), second_model=_AgreeingSecondModel())
    base = {"worked_example": "photosynthesis happens in leaves."}
    outcome = hl.hyperlocalize(
        body=base, locale=LocaleContext(region="in"),
        subject_terms=["photosynthesis"],
    )
    # Withheld: never served a variant that translated the subject term away.
    assert outcome.localized is False
    assert outcome.not_yet_localised is True
    assert outcome.review_reason is not None
    assert "subject-terms" in outcome.review_reason or "subject term" in outcome.review_reason
    # The served fallback is the untouched base content.
    assert "photosynthesis" in outcome.body["worked_example"]


def test_altering_concept_correctness_is_withheld():
    hl = Hyperlocalizer(provider=_ConceptBender(), second_model=_AgreeingSecondModel())
    base = {"expression": "6 * 7", "answer": 42.0}
    outcome = hl.hyperlocalize(
        body=base, locale=LocaleContext(region="in"), subject_terms=[]
    )
    assert outcome.localized is False
    assert outcome.not_yet_localised is True
    # Fallback preserves the correct answer.
    assert outcome.body["answer"] == 42.0


def test_abstaining_second_model_withholds_even_clean_variant():
    """No live second model => abstain => gate closed (fail closed), even for a
    faithful localisation. Proves the gate is honoured, never bypassed."""
    hl = Hyperlocalizer(provider=_RelevanceProvider())  # default abstaining model
    outcome = hl.hyperlocalize(
        body={"worked_example": "photosynthesis.", "answer": 42.0},
        locale=LocaleContext(region="in"),
        subject_terms=["photosynthesis"],
    )
    assert outcome.localized is False
    assert outcome.not_yet_localised is True


# ---------------------------------------------------------------------------
# Board is a FIELD (no board lock-in)
# ---------------------------------------------------------------------------

def test_board_is_a_field_any_label_accepted():
    hl = Hyperlocalizer(
        provider=_RelevanceProvider(), second_model=_AgreeingSecondModel()
    )
    base = {"worked_example": "photosynthesis.", "answer": 42.0}
    # Two arbitrary board labels both work — board is data, not an enum.
    for board in ("example-state-board", "some-other-board", "a-third-board"):
        outcome = hl.hyperlocalize(
            body=base, locale=LocaleContext(board=board, region="in"),
            subject_terms=["photosynthesis"],
        )
        assert outcome.localized is True
        assert outcome.body["hyperlocalization"]["locale"]["board"] == board


# ---------------------------------------------------------------------------
# Wired through generate.py
# ---------------------------------------------------------------------------

def test_generate_option_serves_localised_variant_only_when_verified():
    from app.orchestrator import Orchestrator  # spine via _spine bootstrap

    orch = Orchestrator(second_model=_AgreeingSecondModel())
    gen = ContentGenerator(
        orchestrator=orch,
        localization_provider=_RelevanceProvider(),
        localization_second_model=_AgreeingSecondModel(),
    )
    req = MaterialRequest(
        topic_id="topic-1",
        kind=MaterialKind.PRACTICE_ITEM,
        payload={"expression": "6 * 7", "claimed_answer": 42.0},
        locale=LocaleContext(board="example-state-board", region="in", language="ta"),
        subject_terms=(),  # no subject terms in this math body to preserve
    )
    outcome = gen.generate(req)
    assert outcome.served is True
    assert outcome.material is not None
    # The verified math answer is unchanged AND the surface is localised.
    assert outcome.material.body["answer"] == 42.0
    assert outcome.material.localized is True
    assert "Madurai" in outcome.material.body["worked_example"]


def test_generate_without_locale_is_unaffected():
    from app.orchestrator import Orchestrator

    orch = Orchestrator(second_model=_AgreeingSecondModel())
    gen = ContentGenerator(orchestrator=orch)  # no localization provider, no locale
    req = MaterialRequest(
        topic_id="topic-1",
        kind=MaterialKind.PRACTICE_ITEM,
        payload={"expression": "6 * 7", "claimed_answer": 42.0},
    )
    outcome = gen.generate(req)
    assert outcome.served is True
    assert outcome.material.localized is False
    assert outcome.material.not_yet_localised is False
    assert "hyperlocalization" not in outcome.material.body


def test_generate_with_locale_no_provider_degrades_not_yet_localised():
    from app.orchestrator import Orchestrator

    orch = Orchestrator(second_model=_AgreeingSecondModel())
    gen = ContentGenerator(orchestrator=orch)  # NO localization provider
    req = MaterialRequest(
        topic_id="topic-1",
        kind=MaterialKind.PRACTICE_ITEM,
        payload={"expression": "6 * 7", "claimed_answer": 42.0},
        locale=LocaleContext(board="example-state-board", region="in"),
    )
    outcome = gen.generate(req)
    assert outcome.served is True
    assert outcome.material.not_yet_localised is True
    assert outcome.material.localized is False
    # Still the verified content underneath the marker.
    assert outcome.material.body["answer"] == 42.0
