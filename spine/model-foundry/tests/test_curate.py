"""Curation: safety + verify + balance filtering (INVARIANT 7)."""

from __future__ import annotations

from app.capture import TASK_MASTERY_PREDICT, LearningSignal
from app.curate import Curator

from .conftest import ADULT, CONSENT_ADULT


def _sig(*, sid, inp, out, reward=0.9, admissible=True, verify_passed=None, verify_conf=None):
    return LearningSignal(
        signal_id=sid,
        canonical_uuid=ADULT,
        task_class=TASK_MASTERY_PREDICT,
        input=inp,
        output=out,
        reward=reward,
        consent_ref=CONSENT_ADULT,
        age_tier="adult",
        admissible=admissible,
        verify_passed=verify_passed,
        verify_confidence=verify_conf,
    )


def test_drops_inadmissible():
    cur = Curator()
    clean, rep = cur.curate([_sig(sid="a", inp="i1", out="correct", admissible=False)])
    assert clean == []
    assert rep.dropped_inadmissible == 1


def test_drops_unsafe():
    cur = Curator()
    clean, rep = cur.curate(
        [_sig(sid="a", inp="how to make a bomb", out="correct")]
    )
    assert clean == []
    assert rep.dropped_unsafe == 1


def test_drops_low_confidence():
    cur = Curator(min_reward=0.5)
    clean, rep = cur.curate([_sig(sid="a", inp="i1", out="correct", reward=0.2)])
    assert clean == []
    assert rep.dropped_low_confidence == 1


def test_drops_contradictory_pairs():
    cur = Curator()
    clean, rep = cur.curate(
        [
            _sig(sid="a", inp="same-input", out="correct"),
            _sig(sid="b", inp="same-input", out="incorrect"),
        ]
    )
    assert clean == []
    assert rep.dropped_contradictory == 2


def test_only_verify_passing_become_positive_targets():
    # A signal whose output FAILS generate-and-verify is dropped.
    cur = Curator(verifier=lambda s: (False, 0.1))
    clean, rep = cur.curate([_sig(sid="a", inp="i1", out="correct")])
    assert clean == []
    assert rep.dropped_unverified_positive == 1


def test_verify_passing_kept_and_stamped():
    cur = Curator(verifier=lambda s: (True, 0.95))
    clean, rep = cur.curate([_sig(sid="a", inp="i1", out="correct")])
    assert len(clean) == 1
    assert clean[0].verify_passed is True
    assert clean[0].verify_confidence == 0.95
    assert rep.kept == 1


def test_task_class_balancing_caps_per_class():
    cur = Curator(max_per_class=2, verifier=lambda s: (True, 0.95))
    sigs = [_sig(sid=f"s{i}", inp=f"i{i}", out="correct") for i in range(5)]
    clean, rep = cur.curate(sigs)
    assert len(clean) == 2
    assert rep.balanced_capped == 3
