"""Dashboards: every alert carries the FULL explainability set, alerts are spine
recommendations (never re-minted), and a single bad score never raises an alert.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.dashboards import TopicSpec, build_topic_alert, compose_dashboard
from .conftest import OWNER, T_TRIG_RATIOS, has_no_emoji

DUE = datetime(2026, 7, 1, tzinfo=timezone.utc)

_REQUIRED_EXPLAINABILITY = (
    "evidence_summary",
    "evidence_refs",
    "confidence_band",
    "owner",
    "consequence_of_ignoring",
    "why_am_i_seeing_this",
    "suggested_action",
    "ladder_stage",
)


def _topics():
    return [TopicSpec(topic_id=T_TRIG_RATIOS, topic_label="Trigonometric ratios")]


def test_every_alert_carries_full_explainability(gap_cohort):
    profiles, _ = gap_cohort
    dash = compose_dashboard(
        profiles, _topics(), cohort_label="Section 10-B",
        owner_role="teacher", owner_ref=OWNER, due_date=DUE,
    )
    assert dash.alerts, "a confirmed cohort gap must raise at least one alert"
    for alert in dash.alerts:
        for fieldname in _REQUIRED_EXPLAINABILITY:
            value = getattr(alert, fieldname)
            assert value not in (None, "", []), f"alert missing {fieldname}"
        # Evidence is LINKED, never an opaque claim.
        assert len(alert.evidence_refs) >= 1
        for ref in alert.evidence_refs:
            assert ref.event_id is not None
            assert ref.summary
        # Owner is a role + opaque ref (never PII).
        assert alert.owner.role == "teacher"
        assert alert.owner.ref == OWNER


def test_alert_is_non_consequential_and_never_autofires(gap_cohort):
    """A dashboard 'prepare support material' alert is non-consequential. The
    spine fails closed: a prepare-effect that is not on the safe-automatic
    allow-list lands at 'recommend' (surface it, the human decides). It never
    auto-fires and never sits at 'safe_automatic'. INVARIANT 8 holds."""
    profiles, _ = gap_cohort
    alert = build_topic_alert(
        profiles, topic_id=T_TRIG_RATIOS, topic_label="Trigonometric ratios",
        cohort_label="Section 10-B", owner_role="teacher", owner_ref=OWNER,
    )
    assert alert is not None
    assert alert.is_consequential is False
    # Never auto-fires: a dashboard alert is surfaced/staged for a human, never
    # safe_automatic.
    assert alert.ladder_stage in ("recommend", "prepare")
    assert alert.ladder_stage != "safe_automatic"


def test_single_bad_score_raises_no_alert(single_score_cohort):
    """Never from one score: a lone bad attempt is not a confirmed gap, so the
    dashboard surfaces no alert on it."""
    profiles, _ = single_score_cohort
    dash = compose_dashboard(
        profiles, _topics(), cohort_label="Section 10-B",
        owner_role="teacher", owner_ref=OWNER,
    )
    assert dash.alerts == []


def test_strong_cohort_raises_no_alert(strong_cohort):
    profiles, _ = strong_cohort
    dash = compose_dashboard(
        profiles, _topics(), cohort_label="Section 10-B",
        owner_role="teacher", owner_ref=OWNER,
    )
    assert dash.alerts == []


def test_headline_metrics_resolve_through_semantic_layer(gap_cohort):
    profiles, _ = gap_cohort
    dash = compose_dashboard(
        profiles, _topics(), cohort_label="Section 10-B",
        owner_role="teacher", owner_ref=OWNER,
        coverage={T_TRIG_RATIOS: (2, 4)},
    )
    keys = {m.key for m in dash.headline}
    assert {"topic_mastery", "independence", "confirmed_gap_share", "coverage"} <= keys
    for m in dash.headline:
        assert m.plain_language  # every headline is plain language, never raw-only


def test_dashboard_is_deterministic(gap_cohort):
    profiles, _ = gap_cohort
    d1 = compose_dashboard(profiles, _topics(), cohort_label="Section 10-B",
                           owner_role="teacher", owner_ref=OWNER)
    d2 = compose_dashboard(profiles, _topics(), cohort_label="Section 10-B",
                           owner_role="teacher", owner_ref=OWNER)
    assert [a.suggested_action for a in d1.alerts] == [a.suggested_action for a in d2.alerts]
    assert [m.value for m in d1.headline] == [m.value for m in d2.headline]


def test_degraded_reasons_name_env_vars_only(gap_cohort):
    profiles, _ = gap_cohort
    dash = compose_dashboard(profiles, _topics(), cohort_label="Section 10-B",
                             owner_role="teacher", owner_ref=OWNER)
    # Names only — dotted contract names, never a value.
    for r in dash.degraded_reasons:
        assert r.startswith("clss.intelligence_views.dev.")


def test_alert_text_has_no_emoji_or_exclamation(gap_cohort):
    profiles, _ = gap_cohort
    dash = compose_dashboard(profiles, _topics(), cohort_label="Section 10-B",
                             owner_role="teacher", owner_ref=OWNER)
    for a in dash.alerts:
        for text in (a.evidence_summary, a.consequence_of_ignoring,
                     a.why_am_i_seeing_this, a.suggested_action):
            assert "!" not in text
            assert has_no_emoji(text)
