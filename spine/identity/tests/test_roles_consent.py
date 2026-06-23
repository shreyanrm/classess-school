"""Distinct institution roles and the consent baseline (kept green)."""

from __future__ import annotations

import uuid

import pytest

from typing import get_args

from app.models import Membership, Role

from .conftest import COORDINATOR


def test_new_roles_present_in_model():
    roles = set(get_args(Role))
    for r in ("coordinator", "hod", "examination", "support", "it"):
        assert r in roles
    # The original four remain.
    for r in ("admin", "teacher", "student", "parent"):
        assert r in roles


@pytest.mark.parametrize("role", ["coordinator", "hod", "examination", "support", "it"])
def test_membership_accepts_distinct_roles(role):
    from datetime import datetime, timezone
    m = Membership(app="school", role=role, scope="grade:8",
                   granted_at=datetime.now(timezone.utc))
    assert m.role == role


def test_grant_accepts_distinct_roles(client, bearer):
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    r = client.post("/v1/identity/access-grants", headers=bearer, json={
        "kind": "delegated", "grantee": str(uuid.uuid4()), "granted_by": str(COORDINATOR),
        "app": "school", "role": "hod", "scope": "department:science",
        "expires_at": (now + timedelta(hours=1)).isoformat(),
    })
    assert r.status_code == 201
    assert r.json()["role"] == "hod"


def test_consent_grant_then_check(client, bearer):
    cuid = str(uuid.uuid4())
    g = client.post("/v1/identity/consent/grant", headers=bearer, json={
        "canonical_uuid": cuid, "scope": "learning_behavior", "purpose": "mastery",
        "age_tier": "adult", "granted_by": cuid,
    })
    assert g.status_code == 201
    c = client.post("/v1/identity/consent/check", headers=bearer, json={
        "canonical_uuid": cuid, "scope": "learning_behavior", "purpose": "mastery",
    })
    assert c.json()["satisfied"] is True


def test_consent_check_unsatisfied_when_absent(client, bearer):
    c = client.post("/v1/identity/consent/check", headers=bearer, json={
        "canonical_uuid": str(uuid.uuid4()), "scope": "x", "purpose": "mastery",
    })
    assert c.json()["satisfied"] is False
