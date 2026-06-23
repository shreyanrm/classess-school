"""The consent + purpose access gate (INVARIANT 6).

Every read of the learner graph or evidence store in this module passes through
:func:`evaluate` FIRST. The gate is DENIED-BY-DEFAULT: a read proceeds only when
a satisfied consent grant covers the requested scope AND the requested purpose,
and the grant is neither expired nor revoked.

This is the single law of B8: the Learner record READS governed, consent +
purpose-gated views — never bulk reads, never PII, never an ungated read.

The gate is deliberately self-contained and deterministic so it runs offline:

  - When a remote consent authority (A1/A7) is configured it would be consulted
    through the gateway; with nothing wired the in-process evaluation runs and
    still denies-by-default (it never silently allows because the authority is
    absent — the opposite of fail-open).
  - It is purpose-scoped: a grant for ``communication`` does NOT satisfy a read
    requested for ``mastery``. Purpose travels with every read.
  - It is scope-scoped: a grant for ``portfolio`` does NOT satisfy a read of the
    full mastery profile.
  - Cross-context reads (a viewer who is not the learner) require a grant whose
    audience covers that viewer — the Parent surface is consent-authority and
    partnership, never surveillance, so a parent read is gated like any other.

Nothing here carries PII: subjects, viewers and grant ids are opaque
``canonical_uuid`` / opaque ids only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Iterable, Literal

# The coarse purpose buckets (contracts/src/events/primitives.ts Purpose). A
# learner-record read is one of these; mastery/portfolio/credential reads are
# almost always ``mastery``, but the gate accepts any and matches exactly.
Purpose = Literal[
    "instruction",
    "assessment",
    "mastery",
    "intervention",
    "operations",
    "communication",
    "account",
]

# The data scopes a learner record exposes. A grant names the scopes it covers;
# the gate matches the requested scope exactly (no implicit widening).
ReadScope = Literal[
    "mastery-profile",   # the evidence-linked mastery/gap profile
    "portfolio",         # curated artifacts
    "credentials",       # verifiable credentials
    "evidence-lineage",  # the source events behind an item
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Decision(str, Enum):
    """The gate outcome. Only ALLOW lets a read proceed."""

    ALLOW = "allow"
    DENY = "deny"


@dataclass(frozen=True)
class ConsentGrant:
    """A recorded consent grant the gate evaluates.

    Mirrors the consent contract (contracts/src/events/payloads.ts
    ConsentGrantedPayload) reduced to what the gate needs. Opaque only.

    ``audience`` is the set of opaque viewer ids the grant authorizes to read.
    An empty audience means "self only" — the learner reading their own record.
    ``expires_at`` of ``None`` means no expiry; ``revoked`` overrides everything.
    """

    consent_id: str
    subject: str                       # opaque canonical_uuid of the learner
    scopes: frozenset[ReadScope]
    purposes: frozenset[Purpose]
    audience: frozenset[str] = field(default_factory=frozenset)
    age_tier: Literal["child", "teen", "adult"] = "child"
    granted_by: str | None = None      # opaque ref (self, or guardian)
    expires_at: datetime | None = None
    revoked: bool = False

    def covers_viewer(self, *, subject: str, viewer: str) -> bool:
        """Self-reads are always in-audience; others must be named explicitly."""
        if viewer == subject:
            return True
        return viewer in self.audience

    def is_live(self, *, asof: datetime) -> bool:
        if self.revoked:
            return False
        if self.expires_at is not None and asof >= self.expires_at:
            return False
        return True


@dataclass(frozen=True)
class ReadRequest:
    """A request to read part of a learner record. Opaque only — no PII."""

    subject: str          # opaque canonical_uuid being read
    viewer: str           # opaque canonical_uuid doing the reading
    scope: ReadScope
    purpose: Purpose


@dataclass(frozen=True)
class AccessResult:
    """The gate's verdict, with a plain-language, explainable reason.

    Explainable intelligence (principle 2): every denial says WHY, so a surface
    can render "why am I seeing this / why can I not see this" without leaking a
    number, a formula, or any PII.
    """

    decision: Decision
    reason: str
    consent_id: str | None = None  # the grant that satisfied an ALLOW

    @property
    def allowed(self) -> bool:
        return self.decision is Decision.ALLOW


class ConsentDenied(PermissionError):
    """Raised when a gated read is attempted without a satisfied consent check.

    Subclasses ``PermissionError`` so callers can treat a denial as the access
    failure it is. Carries the explainable reason, never PII.
    """

    def __init__(self, result: AccessResult) -> None:
        self.result = result
        super().__init__(result.reason)


def evaluate(
    request: ReadRequest,
    grants: Iterable[ConsentGrant],
    *,
    asof: datetime | None = None,
) -> AccessResult:
    """Evaluate a read request against the available consent grants.

    DENIED-BY-DEFAULT: returns ALLOW only if SOME live grant matches the
    subject, covers the viewer, includes the requested scope, and includes the
    requested purpose. Otherwise DENY with a specific, PII-free reason.
    """
    asof = asof or _now()

    # We track the closest miss to give the most useful denial reason, without
    # ever leaking which grants exist beyond the requested subject.
    saw_subject_grant = False
    saw_live_grant = False
    saw_audience_match = False
    saw_scope_match = False

    for grant in grants:
        if grant.subject != request.subject:
            continue
        saw_subject_grant = True
        if not grant.is_live(asof=asof):
            continue
        saw_live_grant = True
        if not grant.covers_viewer(subject=request.subject, viewer=request.viewer):
            continue
        saw_audience_match = True
        if request.scope not in grant.scopes:
            continue
        saw_scope_match = True
        if request.purpose not in grant.purposes:
            continue
        return AccessResult(
            decision=Decision.ALLOW,
            reason=(
                f"A live consent grant covers a '{request.scope}' read for the "
                f"'{request.purpose}' purpose."
            ),
            consent_id=grant.consent_id,
        )

    # Denied — pick the most specific reason from how far matching got.
    if not saw_subject_grant:
        reason = "No consent has been recorded for this learner record. Read denied."
    elif not saw_live_grant:
        reason = "The relevant consent has expired or been revoked. Read denied."
    elif not saw_audience_match:
        reason = "This viewer is not in the audience the learner consented to. Read denied."
    elif not saw_scope_match:
        reason = f"Consent does not cover the '{request.scope}' part of this record. Read denied."
    else:
        reason = f"Consent does not cover reads for the '{request.purpose}' purpose. Read denied."
    return AccessResult(decision=Decision.DENY, reason=reason)


def require(
    request: ReadRequest,
    grants: Iterable[ConsentGrant],
    *,
    asof: datetime | None = None,
) -> AccessResult:
    """Like :func:`evaluate` but RAISES :class:`ConsentDenied` on deny.

    The read-side code paths in profile/portfolio/credentials call ``require``
    so that no governed view can be assembled without passing the gate — a read
    without a satisfied consent check cannot proceed.
    """
    result = evaluate(request, grants, asof=asof)
    if not result.allowed:
        raise ConsentDenied(result)
    return result


__all__ = [
    "Purpose",
    "ReadScope",
    "Decision",
    "ConsentGrant",
    "ReadRequest",
    "AccessResult",
    "ConsentDenied",
    "evaluate",
    "require",
]
