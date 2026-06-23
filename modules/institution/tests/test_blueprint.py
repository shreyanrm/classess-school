"""Blueprint wizard: validation, provisioning, and append-only event building."""

from __future__ import annotations

from datetime import date

import pytest

from app.blueprint import (
    Blueprint,
    RosterEntry,
    PolicyDirective,
    BlueprintError,
    provision,
    provisioning_events,
)
from app.events import (
    STRUCTURE_CHANGED,
    ROSTER_CHANGED,
    POLICY_CHANGED,
)
from app.policy import LOCALE_LANGUAGE
from app.tenancy import CrossTenantAccessError, TenantScope


def _minimal_structure() -> list[dict]:
    return [
        {"key": "s", "kind": "school", "label": "Day School", "parent": None},
        {"key": "g10", "kind": "grade", "label": "Grade 10", "parent": "s"},
        {"key": "secA", "kind": "section", "label": "Section 10-A", "parent": "g10"},
    ]


def test_minimal_provisioning_succeeds():
    bp = Blueprint(name="An Institution", structure=_minimal_structure())
    cfg = provision(bp)
    assert cfg.tenant_id  # opaque minted id
    assert cfg.name == "An Institution"
    assert len(cfg.hierarchy.all_nodes()) == 3
    assert isinstance(cfg.scope, TenantScope)
    assert cfg.scope.tenant_id == cfg.tenant_id


def test_provisioning_resolves_roster_to_node_ids():
    bp = Blueprint(
        name="An Institution",
        structure=_minimal_structure(),
        roster=[
            RosterEntry(
                member_uuid="00000000-0000-0000-0000-000000000001",
                node_key="secA",
                role="teacher",
                valid_from=date(2026, 4, 1),
            )
        ],
    )
    cfg = provision(bp)
    assert len(cfg.roster) == 1
    entry = cfg.roster[0]
    # The opaque member id is preserved; the node key resolved to a real node id.
    assert entry["member_uuid"] == "00000000-0000-0000-0000-000000000001"
    assert entry["node_id"] in {n.id for n in cfg.hierarchy.all_nodes()}
    assert entry["role"] == "teacher"


def test_provisioning_applies_policy_and_localization():
    bp = Blueprint(
        name="An Institution",
        structure=_minimal_structure(),
        policies=[
            PolicyDirective(node_key="s", key=LOCALE_LANGUAGE, value="lang-x"),
            PolicyDirective(node_key="s", key="grading.scheme", value="competency"),
        ],
    )
    cfg = provision(bp)
    section_id = next(n.id for n in cfg.hierarchy.all_nodes() if n.kind == "section")
    loc = cfg.localization_for(section_id)
    assert loc.language == "lang-x"  # inherited from the school
    grading = cfg.policies.resolve(section_id, "grading.scheme")
    assert grading.value == "competency"


def test_validation_collects_all_problems():
    bp = Blueprint(
        name="   ",  # blank name
        structure=_minimal_structure(),
        roster=[
            RosterEntry(
                member_uuid="u1", node_key="ghost", role="teacher",
                valid_from=date(2026, 4, 1),
            )
        ],
        policies=[PolicyDirective(node_key="ghost2", key="k", value=1)],
    )
    with pytest.raises(BlueprintError) as exc:
        provision(bp)
    problems = exc.value.problems
    assert any("name is required" in p for p in problems)
    assert any("ghost" in p for p in problems)
    assert any("ghost2" in p for p in problems)


def test_empty_structure_rejected():
    with pytest.raises(BlueprintError):
        provision(Blueprint(name="X", structure=[]))


def test_locked_policy_override_in_blueprint_rejected():
    structure = [
        {"key": "g", "kind": "group", "label": "Example Group", "parent": None},
        {"key": "s", "kind": "school", "label": "Day School", "parent": "g"},
    ]
    bp = Blueprint(
        name="X",
        structure=structure,
        policies=[
            PolicyDirective(node_key="g", key="retention.months", value=36, locked=True),
            PolicyDirective(node_key="s", key="retention.months", value=6),
        ],
    )
    with pytest.raises(BlueprintError) as exc:
        provision(bp)
    assert any("retention.months" in p for p in exc.value.problems)


def test_provisioning_events_are_appendonly_envelopes():
    bp = Blueprint(
        name="An Institution",
        structure=_minimal_structure(),
        roster=[
            RosterEntry(
                member_uuid="00000000-0000-0000-0000-000000000001",
                node_key="secA", role="learner", valid_from=date(2026, 4, 1),
            )
        ],
        policies=[PolicyDirective(node_key="s", key=LOCALE_LANGUAGE, value="lang-x")],
    )
    cfg = provision(bp)
    events = provisioning_events(
        cfg,
        actor_uuid="00000000-0000-0000-0000-0000000000ff",
        consent_ref="11111111-1111-1111-1111-111111111111",
    )
    types = [e["type"] for e in events]
    assert types.count(STRUCTURE_CHANGED) == 3  # one per node
    assert types.count(ROSTER_CHANGED) == 1
    assert types.count(POLICY_CHANGED) == 1  # only where set, not inherited

    for e in events:
        # Attribution shape: opaque identity only, never PII.
        assert e["app"] == "school"
        assert e["canonical_uuid"] == "00000000-0000-0000-0000-0000000000ff"
        assert e["purpose"] == "operations"
        assert e["schema_version"] == "v1"
        # Tenant scope carried on every operational payload (INVARIANT 10).
        assert e["payload"]["institution_id"] == cfg.tenant_id
        # No PII keys leaked into any payload (a structure "label" is a node's
        # own display name, not a person's name, so it is allowed).
        keys = {k.lower() for k in e["payload"]}
        assert "email" not in keys and "phone" not in keys


def test_provisioned_config_scope_isolates_tenant():
    cfg = provision(Blueprint(name="X", structure=_minimal_structure()))
    node = cfg.hierarchy.all_nodes()[0]
    # The config's own scope reads its nodes.
    assert cfg.hierarchy.get_node(node.id, scope=cfg.scope).id == node.id
    # A foreign tenant cannot.
    foreign = TenantScope(tenant_id="other-tenant")
    with pytest.raises(CrossTenantAccessError):
        cfg.hierarchy.get_node(node.id, scope=foreign)


def test_pre_minted_tenant_id_is_honoured():
    cfg = provision(
        Blueprint(name="X", structure=_minimal_structure(), tenant_id="fixed-tenant")
    )
    assert cfg.tenant_id == "fixed-tenant"
