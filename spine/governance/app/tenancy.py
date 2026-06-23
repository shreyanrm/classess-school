"""Tenant isolation policy (spine A7).

INVARIANT 10 — TENANT ISOLATION with logical separation per institution. This
module is the policy that decides whether a request running in one tenant scope
may touch a resource owned by another. The default is DENY: a request sees only
its own tenant and, where the hierarchy explicitly permits, its descendants.

The org graph spans four tiers (group / franchise / programme / network). A
``group`` node may enclose ``franchise`` nodes, and so on. A request scoped to a
parent node may read down into a registered descendant (an inherited,
explicitly-modelled relationship); a request scoped to a child may NEVER read up
into its parent or sideways into a sibling.

This is a pure policy object — no IO, fully deterministic — so the same decision
can be enforced at the gateway wall and asserted in tests. The actual row-level
separation is the database's job; this module is the authoritative yes/no the
wall consults (INVARIANT 3: enforced at the wall, not inside services).
"""

from __future__ import annotations

from uuid import UUID

from .models import TenantContext, TenantTier

# The containment order of the tiers. A higher tier may enclose lower ones; a
# lower tier never encloses a higher one.
_TIER_RANK = {
    TenantTier.NETWORK: 3,
    TenantTier.GROUP: 2,
    TenantTier.FRANCHISE: 1,
    TenantTier.PROGRAMME: 0,
}


class CrossTenantDenied(PermissionError):
    """Raised when a request attempts a read outside its permitted tenant scope."""


class TenancyPolicy:
    """Authoritative tenant-isolation decisions.

    Hierarchy edges are explicit: ``register_parent(child, parent)`` records that
    ``child`` is enclosed by ``parent``. A parent may read into descendants it
    encloses; nothing reads up or sideways.
    """

    def __init__(self) -> None:
        # child_tenant_id -> parent_tenant_id
        self._parents: dict[UUID, UUID] = {}

    def register_parent(self, *, child: UUID, parent: UUID) -> None:
        if child == parent:
            raise ValueError("a tenant cannot be its own parent.")
        self._parents[child] = parent

    def _ancestors(self, tenant_id: UUID) -> list[UUID]:
        chain: list[UUID] = []
        seen: set[UUID] = set()
        cur = self._parents.get(tenant_id)
        while cur is not None and cur not in seen:
            chain.append(cur)
            seen.add(cur)
            cur = self._parents.get(cur)
        return chain

    def can_read(self, *, requester: TenantContext, resource_tenant_id: UUID) -> bool:
        """True iff ``requester`` may read a resource owned by
        ``resource_tenant_id``.

        - Same tenant: allowed.
        - Resource is a descendant of the requester (requester is an ancestor of
          the resource): allowed (read-down).
        - Otherwise (parent, sibling, unrelated): denied.
        """
        if requester.tenant_id == resource_tenant_id:
            return True
        # Allowed only if the requester is an ancestor of the resource's tenant.
        return requester.tenant_id in self._ancestors(resource_tenant_id)

    def assert_read(self, *, requester: TenantContext, resource_tenant_id: UUID) -> None:
        if not self.can_read(requester=requester, resource_tenant_id=resource_tenant_id):
            raise CrossTenantDenied(
                f"tenant {requester.tenant_id} may not read resource owned by "
                f"{resource_tenant_id}: cross-tenant isolation (INVARIANT 10)."
            )

    def can_enclose(self, *, parent_tier: TenantTier, child_tier: TenantTier) -> bool:
        """Structural check: may a node of ``parent_tier`` enclose ``child_tier``?

        A higher-ranked tier may enclose a strictly lower-ranked one.
        """
        return _TIER_RANK[parent_tier] > _TIER_RANK[child_tier]
