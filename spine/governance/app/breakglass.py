"""Break-glass: privileged access (spine A7).

INVARIANT 9 — PRIVILEGED ACTIONS ARE BREAK-GLASS. Opening privileged access:

1. REQUIRES a non-empty human reason. No reason -> ``ReasonRequiredError`` and
   nothing is opened. This is the central law of this module.
2. Is RECORDED IMMUTABLY. Every open writes one privileged audit entry through
   the immutable audit log (no UPDATE/DELETE path). The grant ledger here is
   also append-only; close/review advance state by appending a NEW grant record
   that supersedes the prior one — the original open is never edited.
3. Is REVIEWABLE. ``list_open`` and ``list_for_review`` expose the grants so a
   second qualified person can review them; ``review`` records the reviewer and
   note (again, by appending a superseding record + a privileged audit entry).

Grants are time-boxed (a TTL): an expired grant no longer authorizes access.
Where policy demands four-eyes, an ``approved_by`` second principal is required
to open — ``ApprovalRequiredError`` otherwise (INVARIANT 8: consequential
actions are not unilateral).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import UUID

from .audit import AuditLog
from .models import BreakGlassGrant, new_id

DEFAULT_TTL_SECONDS = 30 * 60  # privileged windows are short by default


class ReasonRequiredError(ValueError):
    """Raised when break-glass is opened without a non-empty reason."""


class ApprovalRequiredError(PermissionError):
    """Raised when a capability requires four-eyes and no approver is supplied."""


class GrantNotFoundError(KeyError):
    """Raised when closing/reviewing a grant id that is not open."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


class BreakGlassService:
    """Open / close / review privileged access, every step audited immutably.

    The grant store is an append-only list; the *current* state of a grant is the
    latest record carrying its ``grant_id``. The audit log is the immutable
    record of every transition.
    """

    def __init__(
        self,
        audit_log: AuditLog,
        *,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        require_approval_for: frozenset[str] | None = None,
    ) -> None:
        self._audit = audit_log
        self._ttl = ttl_seconds
        # Capabilities that demand a second-person approver to open.
        self._require_approval_for = require_approval_for or frozenset()
        self._ledger: list[BreakGlassGrant] = []  # append-only

    # -- open ---------------------------------------------------------------
    async def open(
        self,
        *,
        actor_uuid: UUID,
        capability: str,
        reason: str,
        tenant_id: UUID,
        approved_by: UUID | None = None,
    ) -> BreakGlassGrant:
        # LAW 1: a reason is mandatory. Whitespace is not a reason.
        if reason is None or not str(reason).strip():
            raise ReasonRequiredError(
                "break-glass requires a non-empty reason; privileged access denied."
            )
        # LAW (four-eyes): some capabilities cannot be opened unilaterally.
        if capability in self._require_approval_for and approved_by is None:
            raise ApprovalRequiredError(
                f"capability {capability!r} requires a second-person approver to break glass."
            )

        now = _now()
        grant = BreakGlassGrant(
            grant_id=new_id(),
            actor_uuid=actor_uuid,
            capability=capability,
            reason=reason.strip(),
            tenant_id=tenant_id,
            opened_at=now,
            expires_at=now + timedelta(seconds=self._ttl),
            approved_by=approved_by,
        )
        self._ledger.append(grant)
        # LAW 2: recorded immutably as a privileged audit entry.
        await self._audit.record(
            actor_uuid=actor_uuid,
            action="breakglass.open",
            resource=capability,
            purpose="break-glass",
            tenant_id=tenant_id,
            privileged=True,
            detail={
                "grant_id": str(grant.grant_id),
                "reason": grant.reason,
                "approved_by": str(approved_by) if approved_by else None,
                "expires_at": grant.expires_at.isoformat(),
            },
        )
        return grant

    # -- state lookups ------------------------------------------------------
    def _current(self, grant_id: UUID) -> BreakGlassGrant | None:
        latest: BreakGlassGrant | None = None
        for g in self._ledger:
            if g.grant_id == grant_id:
                latest = g  # later records supersede earlier ones
        return latest

    def is_active(self, grant_id: UUID, *, at: datetime | None = None) -> bool:
        g = self._current(grant_id)
        if g is None or g.closed_at is not None:
            return False
        return (at or _now()) < g.expires_at

    def list_open(self, *, at: datetime | None = None) -> list[BreakGlassGrant]:
        when = at or _now()
        seen: set[UUID] = set()
        out: list[BreakGlassGrant] = []
        for g in reversed(self._ledger):
            if g.grant_id in seen:
                continue
            seen.add(g.grant_id)
            if g.closed_at is None and when < g.expires_at:
                out.append(g)
        out.reverse()
        return out

    def list_for_review(self) -> list[BreakGlassGrant]:
        """All grants that have not yet been reviewed (open or closed)."""
        seen: set[UUID] = set()
        out: list[BreakGlassGrant] = []
        for g in reversed(self._ledger):
            if g.grant_id in seen:
                continue
            seen.add(g.grant_id)
            if g.reviewed_by is None:
                out.append(g)
        out.reverse()
        return out

    # -- close --------------------------------------------------------------
    async def close(self, *, grant_id: UUID, actor_uuid: UUID) -> BreakGlassGrant:
        current = self._current(grant_id)
        if current is None:
            raise GrantNotFoundError(f"no break-glass grant {grant_id}")
        closed = replace(current, closed_at=_now())
        self._ledger.append(closed)  # append a superseding record; original kept
        await self._audit.record(
            actor_uuid=actor_uuid,
            action="breakglass.close",
            resource=current.capability,
            purpose="break-glass",
            tenant_id=current.tenant_id,
            privileged=True,
            detail={"grant_id": str(grant_id)},
        )
        return closed

    # -- review -------------------------------------------------------------
    async def review(
        self, *, grant_id: UUID, reviewed_by: UUID, note: str
    ) -> BreakGlassGrant:
        current = self._current(grant_id)
        if current is None:
            raise GrantNotFoundError(f"no break-glass grant {grant_id}")
        reviewed = replace(current, reviewed_by=reviewed_by, review_note=note)
        self._ledger.append(reviewed)
        await self._audit.record(
            actor_uuid=reviewed_by,
            action="breakglass.review",
            resource=current.capability,
            purpose="break-glass",
            tenant_id=current.tenant_id,
            privileged=True,
            detail={"grant_id": str(grant_id), "note": note},
        )
        return reviewed
