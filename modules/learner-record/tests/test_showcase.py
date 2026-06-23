"""Year-end compilation + student-owned showcase: immutable snapshot, gated share,
learner-controlled, plain-language headline, owner-only items."""

from __future__ import annotations

import pytest

from app.access import ConsentDenied, ConsentGrant, ReadRequest
from app.portfolio import ArtifactProvenance, Portfolio
from app.showcase import build_showcase, compile_year_end, shared_showcase

from .conftest import (
    CONSENT,
    EVENT_1,
    EVENT_2,
    LEARNER_A,
    OUTSIDER,
    T_FRACTIONS,
    T_GEOMETRY,
    TEACHER,
)


def _prov(**over):
    base = dict(
        topic_id=T_GEOMETRY,
        source_event_ids=(EVENT_1, EVENT_2),
        produced_mode="independent",
    )
    base.update(over)
    return ArtifactProvenance(**base)


def _grant(**over):
    base = dict(
        consent_id=CONSENT,
        subject=LEARNER_A,
        scopes=frozenset({"portfolio"}),
        purposes=frozenset({"mastery"}),
        audience=frozenset({TEACHER}),
    )
    base.update(over)
    return ConsentGrant(**base)


def _req(**over):
    base = dict(subject=LEARNER_A, viewer=TEACHER, scope="portfolio", purpose="mastery")
    base.update(over)
    return ReadRequest(**base)


def _portfolio():
    pf = Portfolio(LEARNER_A)
    pf.add(title="Bridge model", content_ref="ref://1", provenance=_prov(), featured=True)
    pf.add(title="Fractions journal", content_ref="ref://2", provenance=_prov(topic_id=T_FRACTIONS))
    return pf


def test_year_end_compiles_immutable_snapshot():
    pf = _portfolio()
    comp = compile_year_end(pf, period="year-2025-26")
    assert comp.subject == LEARNER_A
    assert comp.period == "year-2025-26"
    assert len(comp.artifacts) == 2
    # Snapshot does not move when the live portfolio changes afterwards.
    pf.add(title="Late addition", content_ref="ref://3", provenance=_prov())
    assert len(comp.artifacts) == 2


def test_year_end_lists_distinct_topics_and_featured():
    comp = compile_year_end(_portfolio(), period="y")
    assert set(comp.topic_ids) == {T_GEOMETRY, T_FRACTIONS}
    assert len(comp.featured) == 1


def test_showcase_defaults_to_featured():
    sc = build_showcase(_portfolio(), headline="What I built this year")
    assert len(sc.items) == 1
    assert sc.items[0].title == "Bridge model"


def test_showcase_respects_learner_chosen_order():
    pf = _portfolio()
    ids = [a.artifact_id for a in pf.all()]
    sc = build_showcase(pf, artifact_ids=list(reversed(ids)))
    assert [i.artifact_id for i in sc.items] == list(reversed(ids))


def test_showcase_headline_rejects_a_score():
    with pytest.raises(ValueError):
        build_showcase(_portfolio(), headline="averaged 95%")


def test_showcase_only_owner_artifacts():
    pf = _portfolio()
    other = Portfolio(OUTSIDER)
    stolen = other.add(title="Not mine", content_ref="ref://x", provenance=_prov())
    from app.showcase import Showcase
    import datetime as _dt

    with pytest.raises(ValueError):
        Showcase(
            subject=LEARNER_A,
            headline="",
            items=(stolen,),
            curated_at=_dt.datetime.now(_dt.timezone.utc),
        )


def test_shared_showcase_gated_denied_by_default():
    sc = build_showcase(_portfolio())
    with pytest.raises(ConsentDenied):
        shared_showcase(sc, request=_req(viewer=OUTSIDER), grants=[_grant()])


def test_shared_showcase_returns_when_consented():
    sc = build_showcase(_portfolio(), headline="My year")
    out = shared_showcase(sc, request=_req(), grants=[_grant()])
    assert out.headline == "My year"


def test_owner_self_view_is_in_audience():
    sc = build_showcase(_portfolio())
    # The learner viewing their own showcase needs only a self-grant (empty audience).
    out = shared_showcase(
        sc,
        request=_req(viewer=LEARNER_A),
        grants=[_grant(audience=frozenset())],
    )
    assert out.subject == LEARNER_A
