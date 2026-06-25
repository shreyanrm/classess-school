"""Hierarchy ownership/management/funding overlays + the canonical config events."""

from __future__ import annotations

from datetime import date

import pytest

from app.hierarchy import (
    build_hierarchy,
    OVERLAY_KINDS,
    RELATIONSHIP_KINDS,
)
from app.events import (
    EventEmitter,
    build_configured_payload,
    build_policy_payload,
    INSTITUTION_CONFIGURED,
    POLICY_CHANGED_CANONICAL,
    INSTITUTION_EVENT_TYPES,
)
from app.config import InstitutionSettings
from app.blueprint import Blueprint, provision, provisioning_events


def _hierarchy():
    spec = [
        {"key": "g", "kind": "group", "label": "Example Group", "parent": None},
        {"key": "s", "kind": "school", "label": "Senior School", "parent": "g"},
        {"key": "prog", "kind": "region", "label": "Funded Programme", "parent": None},
    ]
    h = build_hierarchy("tenant-A", spec)
    ids = {n.label: n.id for n in h.all_nodes()}
    return h, ids


def test_overlay_kinds_present_and_are_relationship_kinds():
    for kind in ("ownership", "management", "affiliation", "funding"):
        assert kind in OVERLAY_KINDS
        assert kind in RELATIONSHIP_KINDS


def test_governance_overlays_are_scoped_and_time_bound():
    h, ids = _hierarchy()
    # The group OWNS the school; a programme FUNDS it for one term.
    h.add_relationship(
        kind="ownership", source_id=ids["Example Group"], target_id=ids["Senior School"],
        valid_from=date(2020, 1, 1),
    )
    h.add_relationship(
        kind="funding", source_id=ids["Funded Programme"], target_id=ids["Senior School"],
        valid_from=date(2026, 4, 1), valid_to=date(2026, 10, 1),
    )
    # As of mid-term, the school is both owned and funded (many-to-many overlays).
    overlays = h.overlays_of(ids["Senior School"], as_of=date(2026, 6, 1))
    kinds = {o.kind for o in overlays}
    assert kinds == {"ownership", "funding"}
    # After the funding window, only ownership remains.
    later = h.overlays_of(ids["Senior School"], as_of=date(2027, 1, 1))
    assert {o.kind for o in later} == {"ownership"}


def test_overlays_filters_out_academic_relationships():
    h, ids = _hierarchy()
    h.add_relationship(
        kind="feeder", source_id=ids["Example Group"], target_id=ids["Senior School"],
        valid_from=date(2020, 1, 1),
    )
    h.add_relationship(
        kind="management", source_id=ids["Example Group"], target_id=ids["Senior School"],
        valid_from=date(2020, 1, 1),
    )
    overlays = h.overlays_of(ids["Senior School"])
    # The feeder edge is academic cross-cutting, NOT a governance overlay.
    assert {o.kind for o in overlays} == {"management"}


def test_overlays_rejects_non_overlay_kind_filter():
    h, ids = _hierarchy()
    with pytest.raises(ValueError):
        h.overlays_of(ids["Senior School"], kind="feeder")


def test_configured_payload_is_pii_free_and_scoped():
    payload = build_configured_payload(
        institution_id="tenant-A", name="An Institution",
        node_count=3, member_count=1, policy_count=2,
    )
    assert payload["institution_id"] == "tenant-A"
    assert payload["node_count"] == 3
    keys = {k.lower() for k in payload}
    assert "email" not in keys and "phone" not in keys


def test_policy_payload_carries_effective_date_and_version():
    payload = build_policy_payload(
        institution_id="tenant-A", node_id="n1", key="grading.scheme",
        value="competency", locked=False, action="set",
        effective_from="2026-04-01", version=2,
    )
    assert payload["effective_from"] == "2026-04-01"
    assert payload["version"] == 2


def test_canonical_event_types_registered():
    assert INSTITUTION_CONFIGURED in INSTITUTION_EVENT_TYPES
    assert POLICY_CHANGED_CANONICAL in INSTITUTION_EVENT_TYPES


def test_emit_configured_degrades_to_returned_object():
    emitter = EventEmitter(InstitutionSettings())
    result = emitter.emit_configured(
        canonical_uuid="00000000-0000-0000-0000-0000000000ff",
        consent_ref="11111111-1111-1111-1111-111111111111",
        institution_id="tenant-A", name="An Institution",
        node_count=3, member_count=1, policy_count=0,
    )
    assert result.delivered is False
    assert result.envelope["type"] == INSTITUTION_CONFIGURED
    assert result.envelope["payload"]["name"] == "An Institution"


def test_provisioning_events_lead_with_configured_and_versioned_policy():
    from app.blueprint import PolicyDirective
    from app.policy import LOCALE_LANGUAGE

    bp = Blueprint(
        name="An Institution",
        structure=[
            {"key": "s", "kind": "school", "label": "Day School", "parent": None},
            {"key": "g", "kind": "grade", "label": "Grade 10", "parent": "s"},
        ],
        policies=[
            PolicyDirective(node_key="s", key=LOCALE_LANGUAGE, value="lang-x",
                            effective_from=date(2026, 4, 1)),
        ],
    )
    cfg = provision(bp)
    events = provisioning_events(
        cfg,
        actor_uuid="00000000-0000-0000-0000-0000000000ff",
        consent_ref="11111111-1111-1111-1111-111111111111",
    )
    # The configured event leads.
    assert events[0]["type"] == INSTITUTION_CONFIGURED
    assert events[0]["payload"]["node_count"] == 2
    assert events[0]["payload"]["policy_count"] == 1
    # The policy event carries the effective date + version.
    pol = [e for e in events if e["payload"].get("key") == LOCALE_LANGUAGE]
    assert len(pol) == 1
    assert pol[0]["payload"]["effective_from"] == "2026-04-01"
    assert pol[0]["payload"]["version"] == 1
