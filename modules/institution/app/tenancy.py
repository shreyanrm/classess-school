"""Logical multi-tenancy for the institution module (INVARIANT 10).

Every record the platform stores for an institution carries a tenant scope —
the opaque ``institution_id`` (a UUID, never derived from a name). Cross-tenant
reads are DENIED BY DEFAULT: a caller operating in tenant A can never read a
record stamped tenant B unless an explicit, recorded cross-tenant grant exists.
This is logical isolation in code; the gateway and the row store enforce the
same boundary at the wall (INVARIANT 3 + 10). The two together are defence in
depth, not one instead of the other.

Design notes:
  - The tenant id is OPAQUE. ``new_tenant_id`` mints a random UUID; it is never
    derived from the institution name (mirrors INVARIANT 2 for identity: opaque,
    not derivable).
  - There is no implicit "admin sees all" backdoor. A platform-operations actor
    that legitimately spans tenants does so through an explicit, auditable
    grant (``allow_cross_tenant``), never a silent global read. That keeps the
    most powerful path the best-governed (the laws' principle).
  - This module is pure and import-safe: stdlib only, no I/O, no secret.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Iterable, TypeVar


def new_tenant_id() -> str:
    """Mint a fresh OPAQUE tenant id. Random — never derived from PII or a name."""
    return str(uuid.uuid4())


class CrossTenantAccessError(PermissionError):
    """Raised when a caller in one tenant attempts to read another tenant's
    record without an explicit cross-tenant grant. Denied by default."""

    def __init__(self, actor_tenant: str, record_tenant: str) -> None:
        self.actor_tenant = actor_tenant
        self.record_tenant = record_tenant
        super().__init__(
            "Cross-tenant read denied by default: an actor scoped to one tenant "
            "may not read another tenant's record without an explicit grant."
        )


@dataclass(frozen=True)
class TenantScope:
    """The scope a record is stamped with and a caller operates within.

    A record's scope is its owning ``tenant_id``. A caller's scope additionally
    carries any explicit cross-tenant grants (other tenant ids it is permitted
    to read). The default — no grants — denies every cross-tenant read.
    """

    tenant_id: str
    # Explicit, recorded grants only. Empty -> single-tenant, deny by default.
    cross_tenant_grants: frozenset[str] = field(default_factory=frozenset)

    def can_read(self, record_tenant_id: str) -> bool:
        """True iff this scope may read a record stamped ``record_tenant_id``.

        Same tenant: always. Another tenant: only with an explicit grant.
        """
        if record_tenant_id == self.tenant_id:
            return True
        return record_tenant_id in self.cross_tenant_grants

    def grant(self, *other_tenant_ids: str) -> "TenantScope":
        """Return a NEW scope with additional explicit cross-tenant read grants.

        Immutable: never mutates in place. A grant is an explicit, auditable
        widening — there is no wildcard "all tenants".
        """
        merged = set(self.cross_tenant_grants)
        merged.update(t for t in other_tenant_ids if t and t != self.tenant_id)
        return TenantScope(tenant_id=self.tenant_id, cross_tenant_grants=frozenset(merged))

    def assert_can_read(self, record_tenant_id: str) -> None:
        """Raise :class:`CrossTenantAccessError` if the read is not permitted."""
        if not self.can_read(record_tenant_id):
            raise CrossTenantAccessError(self.tenant_id, record_tenant_id)


T = TypeVar("T")


def tenant_id_of(record: Any) -> str | None:
    """Best-effort extraction of a record's tenant scope.

    Accepts a mapping with ``tenant_id``/``institution_id``, or an object with
    either attribute. Returns ``None`` when the record carries no scope — an
    unscoped record is a defect and callers should treat ``None`` as un-readable.
    """
    if isinstance(record, dict):
        return record.get("tenant_id") or record.get("institution_id")
    for attr in ("tenant_id", "institution_id"):
        value = getattr(record, attr, None)
        if value:
            return str(value)
    return None


def guard_read(scope: TenantScope, record: Any) -> Any:
    """Return ``record`` only if ``scope`` may read it; otherwise raise.

    The single choke point every read should pass through. An unscoped record
    (no tenant) is denied — a record without a scope must never be served.
    """
    rec_tenant = tenant_id_of(record)
    if rec_tenant is None:
        raise CrossTenantAccessError(scope.tenant_id, "<unscoped>")
    scope.assert_can_read(rec_tenant)
    return record


def filter_readable(scope: TenantScope, records: Iterable[T]) -> list[T]:
    """Return only the records this scope may read.

    Unlike :func:`guard_read` this silently drops what the caller may not see —
    the correct behaviour for a list view, where a denied row simply does not
    appear (it is never leaked, and its absence is not an error).
    """
    out: list[T] = []
    for record in records:
        rec_tenant = tenant_id_of(record)
        if rec_tenant is not None and scope.can_read(rec_tenant):
            out.append(record)
    return out
