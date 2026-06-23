"""The wall: the single enforcement pipeline every call passes through.

Order of checks (fail closed at the first failure):

  1. route exists (capability registered)        -> UNKNOWN_ROUTE
  2. authenticated principal (valid token)        -> NO_TOKEN / INVALID_TOKEN
  3. rate limit (principal + route)               -> RATE_LIMITED
  4. request schema validation                    -> SCHEMA_INVALID
  5. RBAC (role permitted)                         -> RBAC_DENIED
  6. ABAC (attribute predicate)                    -> ABAC_DENIED
  7. consent gate (cross-context reads)            -> CONSENT_REQUIRED
  8. permission ladder (consequential -> approval) -> APPROVAL_REQUIRED
  9. child-safety screen (free-text fields)        -> CHILD_SAFETY_BLOCKED
 10. AUDIT (append-only) of allow OR deny, then dispatch

Every decision -- allow or deny -- is audited. Audit events are immutable and
append-only and carry only the opaque ``canonical_uuid``, never PII.

Auth, consent, child-safety and audit are injected so the gateway supplies real
implementations and tests supply fakes. With none supplied the wall degrades to
safe defaults (no auth source -> all tokens invalid; no child-safety -> free
text fails closed; audit -> in-memory ring) so it never silently runs open.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Protocol

from .capabilities import (
    Capability,
    CapabilityRegistry,
    DenyReason,
    Principal,
    RequestContext,
    WallDenied,
)
from .ratelimit import RateLimiter
from .validation import RequestValidationError


# --------------------------------------------------------------------------- #
# Injectable collaborators
# --------------------------------------------------------------------------- #


class TokenVerifier(Protocol):
    """Resolves a bearer token to a Principal, or None if invalid."""

    def verify(self, token: Optional[str]) -> Optional[Principal]: ...


class ConsentChecker(Protocol):
    """Returns True if the principal holds the required consent scope."""

    def has_consent(self, principal: Principal, scope: str) -> bool: ...


class ChildSafetyScreen(Protocol):
    """Returns True if the free text is safe to forward."""

    def is_safe(self, text: str) -> bool: ...


class AuditSink(Protocol):
    def record(self, event: "AuditEvent") -> None: ...


@dataclass(frozen=True)
class AuditEvent:
    # immutable, append-only; carries only opaque ids.
    ts: float
    actor_uuid: str
    route: str
    allowed: bool
    reason: Optional[str]  # DenyReason value when denied, else None


class InMemoryAuditSink:
    """Append-only ring used when no durable sink is wired (degrade target)."""

    def __init__(self) -> None:
        self._events: List[AuditEvent] = []

    def record(self, event: AuditEvent) -> None:
        # append-only: never mutate or remove prior events.
        self._events.append(event)

    @property
    def events(self) -> List[AuditEvent]:
        return list(self._events)


class _DenyAllVerifier:
    """Safe default: with no real auth source, every token is invalid."""

    def verify(self, token: Optional[str]) -> Optional[Principal]:
        return None


class _GrantAllConsent:
    """Default consent: only used when the gateway wires no checker.

    Note: consent still GATES, because the wall only consults this when a scope
    is required; a real deployment must inject a real checker. This default is
    explicit and logged-by-design via the audit reason on cross-context reads.
    """

    def has_consent(self, principal: Principal, scope: str) -> bool:
        return scope in principal.consent_scopes


class _BlockAllChildSafety:
    """Safe default: with no screen wired, free text fails closed."""

    def is_safe(self, text: str) -> bool:
        return False


# --------------------------------------------------------------------------- #
# The wall
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class WallResult:
    allowed: bool
    capability: Capability
    context: RequestContext
    reason: Optional[DenyReason] = None


class Wall:
    def __init__(
        self,
        *,
        registry: CapabilityRegistry,
        limiter: RateLimiter,
        verifier: Optional[TokenVerifier] = None,
        consent: Optional[ConsentChecker] = None,
        child_safety: Optional[ChildSafetyScreen] = None,
        audit: Optional[AuditSink] = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.registry = registry
        self.limiter = limiter
        self.verifier: TokenVerifier = verifier or _DenyAllVerifier()
        self.consent: ConsentChecker = consent or _GrantAllConsent()
        self.child_safety: ChildSafetyScreen = (
            child_safety or _BlockAllChildSafety()
        )
        self.audit: AuditSink = audit or InMemoryAuditSink()
        self._clock = clock
        # ensure route-specific limits are loaded.
        self.registry.apply_rate_limits(self.limiter)

    # -- audit helper --------------------------------------------------- #

    def _audit(self, actor: str, route: str, allowed: bool, reason: Optional[DenyReason]) -> None:
        self.audit.record(
            AuditEvent(
                ts=self._clock(),
                actor_uuid=actor,
                route=route,
                allowed=allowed,
                reason=(reason.value if reason else None),
            )
        )

    def _deny(self, actor: str, route: str, reason: DenyReason, detail: str = "") -> None:
        self._audit(actor, route, allowed=False, reason=reason)
        raise WallDenied(reason, detail)

    # -- the pipeline --------------------------------------------------- #

    def admit(
        self,
        *,
        route: str,
        token: Optional[str],
        payload: Optional[Dict[str, Any]] = None,
        attributes: Optional[Dict[str, Any]] = None,
        cross_context: bool = False,
        approval_token: Optional[str] = None,
    ) -> WallResult:
        """Run a request through every gate. Raise WallDenied on any failure.

        On success returns a :class:`WallResult` and records an allow audit
        event. The actual capability handler is invoked by the caller AFTER a
        successful admit -- handlers stay thin; the wall did the enforcing.
        """
        payload = payload or {}
        attributes = attributes or {}

        # 1. route exists ------------------------------------------------ #
        cap = self.registry.get(route)
        if cap is None:
            # unknown actor id for audit; use a sentinel.
            self._deny("anonymous", route, DenyReason.UNKNOWN_ROUTE)

        # 2. authentication --------------------------------------------- #
        if not token:
            self._deny("anonymous", route, DenyReason.NO_TOKEN)
        principal = self.verifier.verify(token)
        if principal is None:
            self._deny("anonymous", route, DenyReason.INVALID_TOKEN)

        actor = principal.canonical_uuid
        ctx = RequestContext(
            principal=principal,
            route=route,
            payload=payload,
            attributes=attributes,
            cross_context=cross_context,
            approval_token=approval_token,
        )

        # 3. rate limit -------------------------------------------------- #
        rl = self.limiter.check(actor, route)
        if not rl.allowed:
            self._deny(actor, route, DenyReason.RATE_LIMITED, f"retry_after={rl.retry_after:.2f}")

        # 4. schema validation ------------------------------------------ #
        try:
            self.registry.schemas.validate(route, payload)
        except RequestValidationError as exc:
            # detail references paths only, never values.
            self._deny(actor, route, DenyReason.SCHEMA_INVALID, str(exc))

        # 5. RBAC -------------------------------------------------------- #
        if not set(principal.roles) & set(cap.roles):
            self._deny(actor, route, DenyReason.RBAC_DENIED)

        # 6. ABAC -------------------------------------------------------- #
        if cap.abac is not None and not cap.abac(ctx):
            self._deny(actor, route, DenyReason.ABAC_DENIED)

        # 7. consent gate (cross-context reads) -------------------------- #
        if cap.consent_scope is not None and cross_context:
            if not self.consent.has_consent(principal, cap.consent_scope):
                self._deny(actor, route, DenyReason.CONSENT_REQUIRED, cap.consent_scope)

        # 8. permission ladder (consequential -> human approval) --------- #
        if cap.consequential and not approval_token:
            self._deny(actor, route, DenyReason.APPROVAL_REQUIRED)

        # 9. child-safety on free-text fields ---------------------------- #
        for fname in cap.schema.free_text_fields():
            text = payload.get(fname)
            if isinstance(text, str) and text:
                if not self.child_safety.is_safe(text):
                    self._deny(actor, route, DenyReason.CHILD_SAFETY_BLOCKED, fname)

        # 10. allow + audit --------------------------------------------- #
        self._audit(actor, route, allowed=True, reason=None)
        return WallResult(allowed=True, capability=cap, context=ctx, reason=None)
