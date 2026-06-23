"""The assistance ladder — fades support, declares helping vs evaluating."""

from __future__ import annotations

from learning import ladder


def test_ladder_order_matches_contract():
    assert ladder.ASSISTANCE_LADDER == (
        "Learn", "Coach", "Hint", "Work-with-me", "Check-my-work", "Independent",
    )


def test_only_independent_is_evaluating():
    for rung in ladder.ASSISTANCE_LADDER:
        mode = ladder.assistance_mode_of(rung)
        if rung == "Independent":
            assert mode == "evaluating"
            assert ladder.is_unaided_demonstration(rung)
        else:
            assert mode == "helping"
            assert not ladder.is_unaided_demonstration(rung)


def test_attempt_mode_coherence():
    # Only Independent pairs with mode 'independent'; every other rung supported.
    assert ladder.attempt_mode_of("Independent") == "independent"
    for rung in ("Learn", "Coach", "Hint", "Work-with-me", "Check-my-work"):
        assert ladder.attempt_mode_of(rung) == "supported"


def test_support_fades_as_band_rises():
    # No prior rung: a weaker band starts with more support than a stronger one.
    weak = ladder.recommend_rung(band="emerging", independence=0.2)
    strong = ladder.recommend_rung(band="secure", independence=0.6)
    assert ladder.rung_index(strong) > ladder.rung_index(weak)


def test_fade_is_gradual_one_rung_at_a_time():
    # A learner who used Coach but whose band would offer Independent only fades
    # one rung at a time, never jumps to the top.
    rung = ladder.recommend_rung(band="independent", independence=0.9, last_rung_used="Coach")
    assert ladder.rung_index(rung) == ladder.rung_index("Coach") + 1


def test_struggle_steps_support_back_up():
    no_struggle = ladder.recommend_rung(band="developing", independence=0.4, last_rung_used="Hint")
    with_struggle = ladder.recommend_rung(
        band="developing", independence=0.4, last_rung_used="Hint", recent_struggle=True
    )
    assert ladder.rung_index(with_struggle) < ladder.rung_index(no_struggle)


def test_independent_rung_gated_by_independence_floor():
    # High band but low independence must NOT be offered Independent.
    rung = ladder.recommend_rung(band="independent", independence=0.2, last_rung_used="Check-my-work")
    assert rung != "Independent"
    assert rung == "Check-my-work"


def test_state_declares_helping_vs_evaluating():
    helping = ladder.next_state(band="developing", independence=0.3)
    assert helping.mode == "helping"
    assert "helping" in helping.mode_declaration.lower()

    evaluating = ladder.next_state(band="independent", independence=0.8, last_rung_used="Independent")
    assert evaluating.rung == "Independent"
    assert evaluating.mode == "evaluating"
    assert "on your own" in evaluating.mode_declaration.lower()


def test_coherent_attempt_fields():
    assert ladder.coherent_attempt_fields("Independent") == ("independent", "Independent")
    assert ladder.coherent_attempt_fields("Hint") == ("supported", "Hint")
