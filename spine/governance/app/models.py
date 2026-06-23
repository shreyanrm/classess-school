"""Shared records for governance & safety (spine A7).

Dependency-free dataclasses (stdlib only) so the package is import-safe with no
pydantic requirement. Records that represent immutable ledger entries are
``frozen=True`` — the type system itself refuses in-place mutation, mirroring
the append-only / immutable invariants (5, 9) at the boundary.

No record here carries PII. Identity is referenced ONLY by the opaque
``canonical_uuid`` (INVARIANTS 1, 2). Actors are referenced by opaque
``actor_uuid`` refs, never names.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


# ---------------------------------------------------------------------------
# Shared enumerations
# ---------------------------------------------------------------------------
class TenantTier(str, enum.Enum):
    """Tenant isolation scopes across the org graph (INVARIANT 10)."""

    GROUP = "group"
    FRANCHISE = "franchise"
    PROGRAMME = "programme"
    NETWORK = "network"


class PermissionRung(str, enum.Enum):
    """The permission ladder (INVARIANT 8). Consequential actions never auto-fire."""

    RECOMMEND = "recommend"
    PREPARE = "prepare"
    EXECUTE_WITH_PERMISSION = "execute-with-permission"
    SAFE_AUTOMATIC = "safe-automatic"


class SafetyVerdict(str, enum.Enum):
    """Outcome of a child-safety check on a free-text surface (INVARIANT 12 copy
    discipline aside — this is a moderation state, not product copy)."""

    ALLOW = "allow"
    FLAG = "flag"            # moderation flag — content held for review
    BLOCK = "block"          # content refused outright
    CRISIS = "crisis"        # self-harm / abuse / danger signal — escalate now


class EscalationStatus(str, enum.Enum):
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class RetentionAction(str, enum.Enum):
    KEEP = "keep"
    EXPIRE = "expire"            # retention window elapsed — purge the linkable row
    LEGAL_HOLD = "legal-hold"   # retention overridden by an active hold


# ---------------------------------------------------------------------------
# Audit (INVARIANT 9 — audit is immutable)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class AuditRecord:
    """One immutable audit entry. Frozen: never mutated or deleted in place."""

    audit_id: UUID
    actor_uuid: UUID                 # opaque ref to the acting principal
    action: str                      # e.g. "audit.query", "breakglass.open"
    resource: str                    # what was acted on (opaque ref/label)
    purpose: str                     # purpose code the action ran under
    tenant_id: UUID                  # which tenant scope (INVARIANT 10)
    occurred_at: datetime
    recorded_at: datetime
    privileged: bool = False         # true for break-glass / privileged actions
    detail: dict = field(default_factory=dict)


@dataclass(frozen=True)
class AuditQuery:
    """A read over the audit log. Reads never mutate the log."""

    actor_uuid: UUID | None = None
    action: str | None = None
    resource: str | None = None
    tenant_id: UUID | None = None
    privileged_only: bool = False
    since: datetime | None = None
    until: datetime | None = None
    limit: int = 100


# ---------------------------------------------------------------------------
# Break-glass (INVARIANT 9 — privileged actions are break-glass)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class BreakGlassGrant:
    """An immutable record that privileged access was opened.

    A grant CANNOT exist without a non-empty reason — enforced at the service
    boundary (``breakglass.open``). Frozen so it is reviewable, never edited.
    """

    grant_id: UUID
    actor_uuid: UUID
    capability: str                  # the privileged capability accessed
    reason: str                      # mandatory human justification
    tenant_id: UUID
    opened_at: datetime
    expires_at: datetime
    approved_by: UUID | None = None  # second-person approval where required
    closed_at: datetime | None = None
    reviewed_by: UUID | None = None
    review_note: str | None = None


# ---------------------------------------------------------------------------
# Control centre — model usage + confidence gate + emergency disable
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ModelUsageSample:
    """One usage observation. ``track`` is 1 (external) or 2 (proprietary/edge);
    the two are reported separately and never summed into one figure
    (INVARIANT 11)."""

    capability: str
    track: int                       # 1 or 2 — kept distinct in every view
    tier: str                        # "frontier" | "mid" | "edge"
    served: bool                     # passed the confidence gate and was served
    confidence: float                # verifier confidence in [0, 1]
    latency_ms: int
    occurred_at: datetime


@dataclass(frozen=True)
class CapabilityState:
    """The live enable/disable state of a capability (the emergency kill switch)."""

    capability: str
    enabled: bool
    disabled_reason: str | None = None
    disabled_by: UUID | None = None
    changed_at: datetime | None = None


# ---------------------------------------------------------------------------
# Consent / retention / lineage (INVARIANT 6)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ConsentGrant:
    """An active consent. Gates every cross-context read (INVARIANT 6)."""

    consent_id: UUID
    canonical_uuid: UUID             # opaque subject ref — never PII
    purpose: str
    scope: str
    age_tier: str                    # "child" | "teen" | "adult" — gates depth
    granted_by: UUID
    granted_at: datetime
    retention_days: int              # retention window for data under this consent
    revoked_at: datetime | None = None


@dataclass(frozen=True)
class LineageNode:
    """One node in an insight's lineage — where a conclusion came from."""

    node_id: UUID
    kind: str                        # "event" | "model" | "capability" | "consent"
    ref: str                         # opaque ref/label to the source
    detail: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Lineage:
    """Lineage on an insight: the evidence + the consent it was read under + the
    model/capability that produced it. Every insight carries one (A7 mandate)."""

    insight_id: UUID
    canonical_uuid: UUID
    purpose: str
    consent_id: UUID                 # the consent the underlying reads ran under
    confidence: float
    nodes: list[LineageNode] = field(default_factory=list)
    produced_at: datetime | None = None


# ---------------------------------------------------------------------------
# Child safety (INVARIANT 12 — CHILD-SAFETY on every free-text surface)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SafetyAssessment:
    """The result of running a free-text surface through child-safety."""

    assessment_id: UUID
    surface: str                     # which free-text surface produced the text
    canonical_uuid: UUID             # opaque author ref
    verdict: SafetyVerdict
    categories: tuple[str, ...]      # moderation categories that fired
    crisis: bool                     # a crisis signal was detected
    confidence: float
    monitored: bool                  # the surface is monitored (must be True)
    assessed_at: datetime
    rationale: str = ""


@dataclass(frozen=True)
class Escalation:
    """A crisis escalation to a qualified human. Append-only; status advances via
    new records, the original is never mutated."""

    escalation_id: UUID
    assessment_id: UUID
    canonical_uuid: UUID
    surface: str
    status: EscalationStatus
    raised_at: datetime
    note: str = ""


# ---------------------------------------------------------------------------
# Tenancy (INVARIANT 10 — tenant isolation)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TenantContext:
    """The scope a request runs in. Cross-tenant reads are denied by policy."""

    tenant_id: UUID
    tier: TenantTier
    parent_id: UUID | None = None    # the enclosing node, for hierarchy checks


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def new_id() -> UUID:
    """A fresh opaque id (never derived from PII — INVARIANT 2)."""
    return uuid4()
