"""Tenant isolation policy. Pure + deterministic, no network/DB.

INVARIANT 10.
"""

from __future__ import annotations

import pytest

from app.models import TenantContext, TenantTier, new_id
from app.tenancy import CrossTenantDenied, TenancyPolicy


def _ctx(tenant_id, tier=TenantTier.FRANCHISE):
    return TenantContext(tenant_id=tenant_id, tier=tier)


def test_same_tenant_can_read_itself():
    pol = TenancyPolicy()
    t = new_id()
    assert pol.can_read(requester=_ctx(t), resource_tenant_id=t) is True


def test_unrelated_tenant_is_denied():
    pol = TenancyPolicy()
    a, b = new_id(), new_id()
    assert pol.can_read(requester=_ctx(a), resource_tenant_id=b) is False
    with pytest.raises(CrossTenantDenied):
        pol.assert_read(requester=_ctx(a), resource_tenant_id=b)


def test_parent_can_read_descendant():
    pol = TenancyPolicy()
    group, franchise = new_id(), new_id()
    pol.register_parent(child=franchise, parent=group)
    grp_ctx = _ctx(group, TenantTier.GROUP)
    assert pol.can_read(requester=grp_ctx, resource_tenant_id=franchise) is True


def test_child_cannot_read_up_into_parent():
    pol = TenancyPolicy()
    group, franchise = new_id(), new_id()
    pol.register_parent(child=franchise, parent=group)
    fr_ctx = _ctx(franchise, TenantTier.FRANCHISE)
    assert pol.can_read(requester=fr_ctx, resource_tenant_id=group) is False


def test_siblings_cannot_read_each_other():
    pol = TenancyPolicy()
    group, a, b = new_id(), new_id(), new_id()
    pol.register_parent(child=a, parent=group)
    pol.register_parent(child=b, parent=group)
    assert pol.can_read(requester=_ctx(a), resource_tenant_id=b) is False


def test_grandparent_reads_through_the_chain():
    pol = TenancyPolicy()
    network, group, franchise = new_id(), new_id(), new_id()
    pol.register_parent(child=group, parent=network)
    pol.register_parent(child=franchise, parent=group)
    net_ctx = _ctx(network, TenantTier.NETWORK)
    assert pol.can_read(requester=net_ctx, resource_tenant_id=franchise) is True


def test_tier_enclosure_rules():
    pol = TenancyPolicy()
    assert pol.can_enclose(parent_tier=TenantTier.GROUP,
                           child_tier=TenantTier.FRANCHISE) is True
    assert pol.can_enclose(parent_tier=TenantTier.FRANCHISE,
                           child_tier=TenantTier.GROUP) is False


def test_a_tenant_cannot_be_its_own_parent():
    pol = TenancyPolicy()
    t = new_id()
    with pytest.raises(ValueError):
        pol.register_parent(child=t, parent=t)
