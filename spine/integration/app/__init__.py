"""Classess Integration (FLUID) — the two-way standards bridge (spine A6).

A connector framework + standards adapters that let the platform run as the
intelligence layer on top of an existing system, take it over, or just exchange
data — over LTI 1.3, OneRoster 1.2, xAPI/Caliper, QTI, SCORM, Clever/ClassLink,
Ed-Fi, CASE, and an MCP server surface, with connector-health monitoring.

Invariants realised here:
  - PII is dropped at the seam (1, 2): external records carry PII; only an
    opaque, salted ``source_key`` (and, when identity is online, the random
    ``canonical_uuid``) ever crosses a boundary. ``assert_no_pii`` is the hard
    backstop on every cross-boundary object.
  - Every call passes the gateway (3): adapters hold NO credentials; outbound
    effects are described and handed to a governed gateway capability.
  - Secrets are env-only, by NAME (4): see ``config.py`` and the README.
  - Events are immutable, append-only (5): ``events.py`` builds attributed,
    PII-free event inputs and posts them through the gateway; nothing is mutated.
  - Consent gates the relay (6): an activity event refuses to build without a
    ``consent_ref``.
  - Permission ladder (8): consequential connector actions (grade passback,
    LRS forward, deep-linking) are PREPARED + approval-gated, never auto-fired.
  - Two tracks stay separate (11): Track 1 (external endpoints) and the reserved
    Track 2 slot are distinct fields in config.
  - Child-safety (A7) on free text: the MCP surface screens every declared
    free-text field through an injected guard, refusing unscreened input.

The package is import-safe and degrades gracefully with no live endpoints, no
network and no DB.
"""

from __future__ import annotations

from .config import IntegrationSettings, get_settings
from .connector import Capability, Connector, Direction
from .events import (
    ActivityEventContext,
    EmitRefused,
    EventEmitter,
    build_activity_event,
    emit_activity,
)
from .health import ConnectorHealth, HealthRegistry, HealthState, Probe
from .mapping import (
    IdentityResolver,
    OntologyResolver,
    derive_source_key,
    map_identity,
    map_outcome,
    normalize_role,
    strip_pii,
)
from .models import (
    CanonicalRef,
    LearningActivityStatement,
    MappedClass,
    MappedEnrollment,
    MappedOrg,
    MappedOutcome,
    MappedPerson,
    PIILeakError,
    QTIChoice,
    QTIInteraction,
    QTIItem,
    Role,
    RosterImportResult,
    SCORMManifest,
    SCORMResource,
    Standard,
    Verb,
    assert_no_pii,
)
from .registry import ConnectorRegistry

__all__ = [
    # config
    "IntegrationSettings",
    "get_settings",
    # framework
    "Connector",
    "Capability",
    "Direction",
    "ConnectorRegistry",
    # health
    "ConnectorHealth",
    "HealthRegistry",
    "HealthState",
    "Probe",
    # models
    "Standard",
    "Role",
    "Verb",
    "CanonicalRef",
    "MappedOrg",
    "MappedClass",
    "MappedPerson",
    "MappedEnrollment",
    "MappedOutcome",
    "RosterImportResult",
    "LearningActivityStatement",
    "QTIItem",
    "QTIChoice",
    "QTIInteraction",
    "SCORMManifest",
    "SCORMResource",
    "PIILeakError",
    "assert_no_pii",
    # mapping
    "derive_source_key",
    "map_identity",
    "map_outcome",
    "normalize_role",
    "strip_pii",
    "IdentityResolver",
    "OntologyResolver",
    # events
    "ActivityEventContext",
    "EventEmitter",
    "EmitRefused",
    "build_activity_event",
    "emit_activity",
]
