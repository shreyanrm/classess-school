"""Portfolio: provenance required, gated shared view, append-only curation."""

from __future__ import annotations

import pytest

from app.access import ConsentDenied, ConsentGrant, ReadRequest
from app.portfolio import ArtifactProvenance, Portfolio

from .conftest import CONSENT, EVENT_1, EVENT_2, LEARNER_A, OUTSIDER, T_GEOMETRY, TEACHER


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


def test_artifact_requires_provenance():
    with pytest.raises(ValueError):
        ArtifactProvenance(topic_id=T_GEOMETRY, source_event_ids=(), produced_mode="independent")


def test_add_artifact_keeps_provenance_and_mode():
    pf = Portfolio(LEARNER_A)
    art = pf.add(title="Bridge model", content_ref="ref://obj/1", provenance=_prov())
    assert art.provenance.produced_mode == "independent"
    assert art.provenance.source_event_ids == (EVENT_1, EVENT_2)
    assert art.subject == LEARNER_A


def test_caption_rejects_a_raw_score():
    pf = Portfolio(LEARNER_A)
    with pytest.raises(ValueError):
        pf.add(
            title="Essay",
            content_ref="ref://obj/2",
            provenance=_prov(),
            caption="graded 95%",
        )


def test_shared_view_is_gated_denied_by_default():
    pf = Portfolio(LEARNER_A)
    pf.add(title="Bridge model", content_ref="ref://obj/1", provenance=_prov())
    with pytest.raises(ConsentDenied):
        pf.shared_view(request=_req(viewer=OUTSIDER), grants=[_grant()])


def test_shared_view_returns_artifacts_when_consented():
    pf = Portfolio(LEARNER_A)
    pf.add(title="Bridge model", content_ref="ref://obj/1", provenance=_prov())
    pf.add(title="Proof", content_ref="ref://obj/2", provenance=_prov(), featured=True)
    shared = pf.shared_view(request=_req(), grants=[_grant()])
    assert len(shared) == 2
    featured = pf.shared_view(request=_req(), grants=[_grant()], featured_only=True)
    assert len(featured) == 1
    assert featured[0].title == "Proof"


def test_curation_is_append_only():
    pf = Portfolio(LEARNER_A)
    pf.add(title="A", content_ref="ref://a", provenance=_prov())
    pf.add(title="B", content_ref="ref://b", provenance=_prov())
    assert [a.title for a in pf.all()] == ["A", "B"]
