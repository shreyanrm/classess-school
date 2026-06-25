"""The institution blueprint wizard (B1) — Ring 0 minimal provisioning, real.

Minimal provisioning (institution + structure + roster) is the Ring 0 prerequisite
every other module hangs off; the schema is canonical even while the UI is thin.
This wizard takes a board-agnostic blueprint — structure (the node ladder),
roster (opaque members in scoped, time-bound roles), and policy (settings +
hyperlocalization) — VALIDATES it, and produces a tenant-scoped
``InstitutionConfig`` plus the append-only provisioning events.

The wizard is a multi-step composition with a single validation gate so a
half-built institution is never provisioned:

    1. identity   — mint/accept the opaque tenant id (INVARIANT 2: opaque).
    2. structure  — build the containment tree + relationship graph (hierarchy).
    3. roster     — attach opaque members in scoped, time-bound roles (INVARIANT
                    1 + 2: canonical_uuid only, never a name).
    4. policy     — set + lock policies and hyperlocalization (policy module).
    5. validate   — every roster scope points at a real node; every policy node
                    exists; no locked-policy override; at least one root.

Provisioning is a PREPARE-class action: it builds and validates the config and
RETURNS the events. It does not send/publish anything itself — emitting through
the gateway requires the wiring + (for consequential changes) human approval
(INVARIANT 8, the permission ladder). The wizard hands the caller the events to
emit; it never auto-fires them.

Pure, import-safe: stdlib only; composes the sibling app modules.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

from .hierarchy import Hierarchy, Node, build_hierarchy
from .policy import PolicySet, PolicyError, LocalizationConfig
from .tenancy import TenantScope, new_tenant_id


class BlueprintError(ValueError):
    """The blueprint failed validation — a half-built institution was refused."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("Blueprint validation failed:\n  - " + "\n  - ".join(problems))


@dataclass(frozen=True)
class RosterEntry:
    """One opaque member in a scoped, time-bound role.

    INVARIANT 1 + 2: ``member_uuid`` is the opaque ``canonical_uuid`` — never a
    name/email. ``node_key`` scopes the role to a node in the structure;
    ``role`` is an opaque operational label (e.g. "principal", "teacher",
    "learner"). ``valid_from``/``valid_to`` make the assignment time-bound, so a
    role can lapse on an enrolment/employment change (role removal immediate).
    """

    member_uuid: str
    node_key: str
    role: str
    valid_from: date
    valid_to: Optional[date] = None

    def __post_init__(self) -> None:
        if self.valid_to is not None and self.valid_to <= self.valid_from:
            raise ValueError("Roster entry valid_to must be strictly after valid_from.")


@dataclass(frozen=True)
class PolicyDirective:
    """A policy to set during provisioning, scoped to a node by its stable key.

    ``effective_from`` (optional) stages the version's start date — omit it to
    take effect immediately. ``note`` is an optional human reason for the audit
    trail."""

    node_key: str
    key: str
    value: Any
    locked: bool = False
    effective_from: Optional[date] = None
    note: Optional[str] = None


@dataclass(frozen=True)
class Blueprint:
    """The board-agnostic input to the wizard.

    ``structure`` is the flat, ordered node spec (see hierarchy.build_hierarchy):
    each entry has ``key`` / ``kind`` / ``label`` / ``parent`` / ``attributes``.
    ``roster`` and ``policies`` reference nodes by their stable ``key``.
    """

    name: str
    structure: list[dict]
    roster: list[RosterEntry] = field(default_factory=list)
    policies: list[PolicyDirective] = field(default_factory=list)
    tenant_id: Optional[str] = None  # accept a pre-minted id, else mint opaque.


@dataclass(frozen=True)
class InstitutionConfig:
    """The validated, tenant-scoped output of provisioning.

    Holds the opaque tenant id, the built hierarchy, the policy set, the resolved
    roster (keyed to opaque node ids), and a default :class:`TenantScope` for the
    institution. This is the canonical Ring 0 artifact.
    """

    tenant_id: str
    name: str
    hierarchy: Hierarchy
    policies: PolicySet
    # member_uuid + opaque node id + role + window (keys resolved to node ids).
    roster: list[dict]
    scope: TenantScope

    def localization_for(self, node_id: str) -> LocalizationConfig:
        """The resolved hyperlocalization (language/region/calendar) for a node."""
        return LocalizationConfig.from_policy_set(self.policies, node_id)


def provision(blueprint: Blueprint) -> InstitutionConfig:
    """Run the wizard end to end and return a validated :class:`InstitutionConfig`.

    Raises :class:`BlueprintError` with ALL problems collected (not just the
    first) so the thin UI can show everything to fix at once. Provisioning is
    deterministic and offline — no network, no secret.
    """
    problems: list[str] = []

    # 1. identity — opaque tenant id.
    tenant_id = blueprint.tenant_id or new_tenant_id()

    if not blueprint.name or not blueprint.name.strip():
        problems.append("Institution name is required.")
    if not blueprint.structure:
        problems.append("Structure must define at least one node.")

    # 2. structure — build the tree (catch structural errors as problems).
    hierarchy: Optional[Hierarchy] = None
    key_to_id: dict[str, str] = {}
    try:
        hierarchy = build_hierarchy(tenant_id, blueprint.structure)
        # Recover the key -> id mapping for roster/policy resolution.
        # build_hierarchy mints ids; re-derive by matching label+kind+order.
        key_to_id = _rederive_keys(blueprint.structure, hierarchy)
    except Exception as exc:  # structural rule violation
        problems.append(f"Structure invalid: {exc}")

    if hierarchy is not None and not hierarchy.roots():
        problems.append("Structure must have at least one root node.")

    # 3 + 4. roster + policy validation needs a built hierarchy.
    policies = PolicySet(hierarchy) if hierarchy is not None else None
    resolved_roster: list[dict] = []

    if hierarchy is not None and policies is not None:
        # Roster: every entry's node_key must resolve to a real node.
        for i, entry in enumerate(blueprint.roster):
            node_id = key_to_id.get(entry.node_key)
            if node_id is None:
                problems.append(
                    f"Roster entry #{i} references unknown node key "
                    f"{entry.node_key!r}."
                )
                continue
            resolved_roster.append(
                {
                    "member_uuid": entry.member_uuid,
                    "node_id": node_id,
                    "role": entry.role,
                    "valid_from": entry.valid_from.isoformat(),
                    "valid_to": entry.valid_to.isoformat() if entry.valid_to else None,
                }
            )

        # Policy: every directive's node must exist; locked-override rejected.
        for i, directive in enumerate(blueprint.policies):
            node_id = key_to_id.get(directive.node_key)
            if node_id is None:
                problems.append(
                    f"Policy directive #{i} references unknown node key "
                    f"{directive.node_key!r}."
                )
                continue
            try:
                policies.set_policy(
                    node_id,
                    directive.key,
                    directive.value,
                    locked=directive.locked,
                    effective_from=directive.effective_from,
                    note=directive.note,
                )
            except PolicyError as exc:
                problems.append(f"Policy directive #{i} rejected: {exc}")

    if problems:
        raise BlueprintError(problems)

    assert hierarchy is not None and policies is not None  # validated above
    return InstitutionConfig(
        tenant_id=tenant_id,
        name=blueprint.name.strip(),
        hierarchy=hierarchy,
        policies=policies,
        roster=resolved_roster,
        scope=TenantScope(tenant_id=tenant_id),
    )


def _rederive_keys(spec: list[dict], hierarchy: Hierarchy) -> dict[str, str]:
    """Map each spec ``key`` to the opaque node id build_hierarchy minted.

    build_hierarchy inserts nodes in spec order; we replay the same order over
    the hierarchy's nodes to pair keys with ids deterministically. (The
    hierarchy preserves insertion order in its node dict.)
    """
    node_ids_in_order = [n.id for n in hierarchy.all_nodes()]
    mapping: dict[str, str] = {}
    for entry, node_id in zip(spec, node_ids_in_order):
        mapping[entry["key"]] = node_id
    return mapping


def provisioning_events(
    config: InstitutionConfig,
    *,
    actor_uuid: str,
    consent_ref: str,
) -> list[dict]:
    """Build (do NOT send) the append-only provisioning events for a config.

    Returns the structure / roster / policy event envelopes the caller would
    emit through the gateway. This is a PREPARE-class step (INVARIANT 8): it
    never sends; the caller (with the wiring and any required human approval)
    decides whether and when to emit. Built here so the events stay coherent
    with the validated config.

    ``actor_uuid`` is the opaque ``canonical_uuid`` of the human provisioning the
    institution — never a name (INVARIANT 1 + 2).
    """
    from . import events as ev  # lazy: keep blueprint import-light

    out: list[dict] = []

    # Configured event — the one-shot "the digital twin exists" summary, first.
    policy_count = sum(
        len(config.policies.set_versions(node.id))
        for node in config.hierarchy.all_nodes()
    )
    out.append(
        ev.build_envelope(
            canonical_uuid=actor_uuid,
            consent_ref=consent_ref,
            payload=ev.build_configured_payload(
                institution_id=config.tenant_id,
                name=config.name,
                node_count=len(config.hierarchy.all_nodes()),
                member_count=len(config.roster),
                policy_count=policy_count,
            ),
            event_type=ev.INSTITUTION_CONFIGURED,
        )
    )

    # Structure events — one per node, parents before children (node order).
    for node in config.hierarchy.all_nodes():
        out.append(
            ev.build_envelope(
                canonical_uuid=actor_uuid,
                consent_ref=consent_ref,
                payload=ev.build_structure_payload(
                    institution_id=config.tenant_id,
                    node_id=node.id,
                    node_kind=node.kind,
                    action="created",
                    parent_id=node.parent_id,
                    label=node.label,
                ),
                event_type=ev.STRUCTURE_CHANGED,
            )
        )

    # Roster events — opaque members in scoped, time-bound roles.
    for entry in config.roster:
        out.append(
            ev.build_envelope(
                canonical_uuid=actor_uuid,
                consent_ref=consent_ref,
                payload=ev.build_roster_payload(
                    institution_id=config.tenant_id,
                    node_id=entry["node_id"],
                    member_uuid=entry["member_uuid"],
                    role=entry["role"],
                    action="enrolled",
                    valid_from=entry["valid_from"],
                    valid_to=entry["valid_to"],
                ),
                event_type=ev.ROSTER_CHANGED,
            )
        )

    # Policy events — one per node's effective set (only locally set values).
    for node in config.hierarchy.all_nodes():
        for key, resolved in config.policies.effective(node.id).items():
            if resolved.inherited:
                continue  # emit only where the value was SET, not where inherited
            out.append(
                ev.build_envelope(
                    canonical_uuid=actor_uuid,
                    consent_ref=consent_ref,
                    payload=ev.build_policy_payload(
                        institution_id=config.tenant_id,
                        node_id=node.id,
                        key=key,
                        value=resolved.value,
                        locked=resolved.locked,
                        action="set",
                        effective_from=resolved.effective_from.isoformat(),
                        version=resolved.version,
                    ),
                    event_type=ev.POLICY_CHANGED,
                )
            )

    return out
