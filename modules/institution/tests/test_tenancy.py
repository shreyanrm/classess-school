"""Tenant isolation: cross-tenant reads denied by default (INVARIANT 10)."""

from __future__ import annotations

import pytest

from app.tenancy import (
    TenantScope,
    CrossTenantAccessError,
    new_tenant_id,
    guard_read,
    filter_readable,
    tenant_id_of,
)


def test_tenant_id_is_opaque_and_unique():
    a, b = new_tenant_id(), new_tenant_id()
    assert a != b
    # Opaque: a UUID, not derived from any name.
    assert len(a) == 36 and a.count("-") == 4


def test_same_tenant_read_allowed():
    scope = TenantScope(tenant_id="tenant-A")
    record = {"tenant_id": "tenant-A", "node_id": "n1"}
    assert guard_read(scope, record) is record


def test_cross_tenant_read_denied_by_default():
    scope = TenantScope(tenant_id="tenant-A")
    record = {"tenant_id": "tenant-B", "node_id": "n1"}
    assert scope.can_read("tenant-B") is False
    with pytest.raises(CrossTenantAccessError):
        guard_read(scope, record)


def test_explicit_grant_widens_read():
    scope = TenantScope(tenant_id="tenant-A").grant("tenant-B")
    record = {"tenant_id": "tenant-B", "node_id": "n1"}
    assert scope.can_read("tenant-B") is True
    assert guard_read(scope, record) is record
    # Still denies a third tenant with no grant.
    assert scope.can_read("tenant-C") is False


def test_grant_is_immutable():
    base = TenantScope(tenant_id="tenant-A")
    widened = base.grant("tenant-B")
    assert base.can_read("tenant-B") is False  # original untouched
    assert widened.can_read("tenant-B") is True


def test_grant_never_includes_wildcard_or_self():
    scope = TenantScope(tenant_id="tenant-A").grant("tenant-A", "tenant-B", "")
    # Granting self/empty is a no-op; only real other-tenant grants land.
    assert scope.cross_tenant_grants == frozenset({"tenant-B"})


def test_unscoped_record_is_denied():
    scope = TenantScope(tenant_id="tenant-A")
    with pytest.raises(CrossTenantAccessError):
        guard_read(scope, {"node_id": "n1"})  # no tenant stamp -> never served


def test_institution_id_treated_as_tenant_scope():
    scope = TenantScope(tenant_id="tenant-A")
    record = {"institution_id": "tenant-A", "node_id": "n1"}
    assert tenant_id_of(record) == "tenant-A"
    assert guard_read(scope, record) is record


def test_filter_readable_drops_foreign_silently():
    scope = TenantScope(tenant_id="tenant-A")
    records = [
        {"tenant_id": "tenant-A", "id": 1},
        {"tenant_id": "tenant-B", "id": 2},
        {"tenant_id": "tenant-A", "id": 3},
        {"id": 4},  # unscoped -> dropped
    ]
    readable = filter_readable(scope, records)
    assert [r["id"] for r in readable] == [1, 3]
