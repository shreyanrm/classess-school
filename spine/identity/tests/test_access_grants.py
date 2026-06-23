"""Delegated / temporary / substitute access as first-class time-bound grants.

A grant must surface as a membership for the grantee while in-window, vanish
outside the window, and be revocable immediately."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from .conftest import COORDINATOR, SUBSTITUTE


def _grant_body(*, starts_at=None, expires_at=None, kind="substitute"):
    now = datetime.now(timezone.utc)
    return {
        "kind": kind,
        "grantee": str(SUBSTITUTE),
        "granted_by": str(COORDINATOR),
        "app": "school",
        "role": "teacher",
        "scope": "grade:6/section:B",
        "starts_at": (starts_at or now - timedelta(minutes=1)).isoformat(),
        "expires_at": (expires_at or now + timedelta(hours=2)).isoformat(),
        "reason": "cover for absence",
    }


@pytest.mark.parametrize("kind", ["delegated", "temporary", "substitute"])
def test_create_grant_kinds(client, bearer, kind):
    r = client.post("/v1/identity/access-grants", headers=bearer, json=_grant_body(kind=kind))
    assert r.status_code == 201
    body = r.json()
    assert body["kind"] == kind
    assert body["active"] is True
    assert body["expires_at"] is not None  # never open-ended


def test_active_grant_surfaces_as_membership(client, bearer):
    # Mint a token for the substitute and resolve their memberships.
    create = client.post("/v1/identity/access-grants", headers=bearer, json=_grant_body())
    assert create.status_code == 201

    sub_token, _, _ = client.app.state.tokens.mint(
        canonical_uuid=SUBSTITUTE, app="school", memberships=[])
    sub_headers = {"Authorization": f"Bearer {sub_token}"}
    res = client.get("/v1/identity/memberships/resolve", headers=sub_headers, params={"app": "school"})
    assert res.status_code == 200
    roles = [m["role"] for m in res.json()]
    assert "teacher" in roles


def test_future_grant_is_not_yet_active(client, bearer):
    now = datetime.now(timezone.utc)
    r = client.post("/v1/identity/access-grants", headers=bearer,
                    json=_grant_body(starts_at=now + timedelta(hours=1),
                                     expires_at=now + timedelta(hours=2)))
    assert r.json()["active"] is False

    sub_token, _, _ = client.app.state.tokens.mint(
        canonical_uuid=SUBSTITUTE, app="school", memberships=[])
    res = client.get("/v1/identity/memberships/resolve",
                     headers={"Authorization": f"Bearer {sub_token}"})
    # Not active yet -> not surfaced.
    assert res.json() == []


def test_expired_grant_not_surfaced(client, bearer):
    now = datetime.now(timezone.utc)
    client.post("/v1/identity/access-grants", headers=bearer,
                json=_grant_body(starts_at=now - timedelta(hours=2),
                                 expires_at=now - timedelta(hours=1)))
    sub_token, _, _ = client.app.state.tokens.mint(
        canonical_uuid=SUBSTITUTE, app="school", memberships=[])
    res = client.get("/v1/identity/memberships/resolve",
                     headers={"Authorization": f"Bearer {sub_token}"})
    assert res.json() == []


def test_revoke_grant_removes_membership_immediately(client, bearer):
    create = client.post("/v1/identity/access-grants", headers=bearer, json=_grant_body())
    grant_id = create.json()["grant_id"]
    rev = client.post(f"/v1/identity/access-grants/{grant_id}/revoke", headers=bearer)
    assert rev.status_code == 204

    sub_token, _, _ = client.app.state.tokens.mint(
        canonical_uuid=SUBSTITUTE, app="school", memberships=[])
    res = client.get("/v1/identity/memberships/resolve",
                     headers={"Authorization": f"Bearer {sub_token}"})
    assert res.json() == []


def test_reject_inverted_window(client, bearer):
    now = datetime.now(timezone.utc)
    r = client.post("/v1/identity/access-grants", headers=bearer,
                    json=_grant_body(starts_at=now + timedelta(hours=2),
                                     expires_at=now + timedelta(hours=1)))
    assert r.status_code == 422


def test_list_grants_by_grantee(client, bearer):
    client.post("/v1/identity/access-grants", headers=bearer, json=_grant_body())
    lst = client.get("/v1/identity/access-grants", headers=bearer,
                     params={"grantee": str(SUBSTITUTE)})
    assert lst.status_code == 200
    assert len(lst.json()) == 1


def test_revoke_unknown_grant_404(client, bearer):
    r = client.post(f"/v1/identity/access-grants/{uuid.uuid4()}/revoke", headers=bearer)
    assert r.status_code == 404
