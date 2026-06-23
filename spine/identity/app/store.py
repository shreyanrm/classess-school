"""Data layer for the identity service.

Two stores, kept logically distinct exactly as the migrations do:
  - the PII pii_vault  (schema ``pii_vault``, table ``pii_vault.users``) — the ONLY place
    canonical_uuid maps to a person;
  - the platform-canonical tables (schema ``platform``: app_memberships,
    consents) — opaque canonical_uuid only, NO PII.

The concrete adapter talks to Postgres via asyncpg. If ``asyncpg`` is not
installed or ``database_url`` is unset, the service falls back to an in-memory
adapter that implements the SAME interface so the API is fully exercisable
without a live Supabase. The in-memory adapter is clearly labelled and refuses
to pretend it is durable.

INVARIANTS enforced here:
  - canonical_uuid is generated with ``uuid4`` (random/opaque, never derived
    from PII) — INVARIANT 2.
  - the pii_vault and the behavioral tables are never joined by SQL FK; the link is
    the shared opaque value only — INVARIANT 1.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

logger = logging.getLogger("clss.identity.store")

try:  # Guarded: missing driver must not crash import.
    import asyncpg  # type: ignore

    _ASYNCPG_AVAILABLE = True
except Exception:  # pragma: no cover - import guard
    asyncpg = None  # type: ignore
    _ASYNCPG_AVAILABLE = False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _grant_active(rec: dict[str, Any]) -> bool:
    """A time-bound grant is active iff it is not revoked and now is within its
    [starts_at, expires_at] window. These grants are NEVER open-ended."""
    if rec.get("revoked_at") is not None:
        return False
    now = _now()
    starts = rec["starts_at"]
    expires = rec["expires_at"]
    return starts <= now <= expires


def _derive_age_tier(dob: str | None) -> str:
    """Non-identifying age tier from a dob. The tier crosses the boundary; the
    dob never does."""
    if not dob:
        return "adult"
    try:
        born = datetime.fromisoformat(dob)
    except ValueError:
        return "adult"
    years = (_now() - born.replace(tzinfo=timezone.utc)).days / 365.25
    if years < 13:
        return "child"
    if years < 18:
        return "teen"
    return "adult"


class IdentityStore(ABC):
    """The interface the API depends on. Both adapters implement it."""

    backend: str

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def close(self) -> None: ...

    # --- Vault (PII) -----------------------------------------------------
    @abstractmethod
    async def issue_canonical_user(self, *, phone: str | None, full_name: str | None,
                                   dob: str | None, email: str | None) -> UUID:
        """Create (or return existing-by-phone) a pii_vault row and return the opaque
        canonical_uuid. PII is written ONLY here."""

    @abstractmethod
    async def resolve_by_phone(self, phone: str) -> UUID | None:
        """Map a phone to its opaque canonical_uuid for OTP login. Stays inside
        the pii_vault boundary."""

    @abstractmethod
    async def age_tier_for(self, canonical_uuid: UUID) -> str: ...

    # --- Memberships (platform-canonical, no PII) ------------------------
    @abstractmethod
    async def active_memberships(self, canonical_uuid: UUID, app: str | None = None) -> list[dict[str, Any]]: ...

    # --- Consent (platform-canonical, no PII) ----------------------------
    @abstractmethod
    async def grant_consent(self, *, canonical_uuid: UUID, scope: str, purpose: str,
                            age_tier: str, granted_by: UUID) -> dict[str, Any]: ...

    @abstractmethod
    async def check_consent(self, *, canonical_uuid: UUID, scope: str, purpose: str) -> dict[str, Any]: ...

    # --- SSO federation (vault) -----------------------------------------
    @abstractmethod
    async def resolve_by_federation(self, *, provider: str, subject: str) -> UUID | None:
        """Map a provider+subject to its opaque canonical_uuid, or None if first
        signup. The provider subject is vaulted; never crosses the boundary."""

    @abstractmethod
    async def link_federation(self, *, canonical_uuid: UUID, provider: str, subject: str,
                              email: str | None, full_name: str | None) -> None:
        """Record a federation link for an existing canonical identity. Vault only."""

    # --- Devices & session risk (platform-canonical, no PII) -------------
    @abstractmethod
    async def register_device(self, *, canonical_uuid: UUID, device_fingerprint: str,
                              label: str | None, platform: str | None) -> dict[str, Any]: ...

    @abstractmethod
    async def list_devices(self, canonical_uuid: UUID) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def revoke_device(self, *, canonical_uuid: UUID, device_id: UUID) -> bool: ...

    @abstractmethod
    async def record_session_risk(self, *, canonical_uuid: UUID, session_id: UUID,
                                  risk: str, signals: list[str], device_id: UUID | None) -> dict[str, Any]: ...

    # --- Access history (platform-canonical, no PII) ---------------------
    @abstractmethod
    async def record_access(self, *, canonical_uuid: UUID, action: str, outcome: str,
                            app: str | None = None, scope: str | None = None,
                            device_id: UUID | None = None, session_id: UUID | None = None,
                            risk: str | None = None) -> dict[str, Any]: ...

    @abstractmethod
    async def access_history(self, canonical_uuid: UUID, *, limit: int = 100) -> list[dict[str, Any]]: ...

    # --- Time-bound access grants (platform-canonical, no PII) -----------
    @abstractmethod
    async def create_access_grant(self, *, kind: str, grantee: UUID, granted_by: UUID,
                                  app: str, role: str, scope: str, starts_at: datetime,
                                  expires_at: datetime, reason: str | None) -> dict[str, Any]: ...

    @abstractmethod
    async def list_access_grants(self, *, grantee: UUID | None = None,
                                 granted_by: UUID | None = None) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def revoke_access_grant(self, *, grant_id: UUID) -> bool: ...


class PostgresIdentityStore(IdentityStore):
    """asyncpg-backed adapter. Mirrors db/migrations 0002 + 0003."""

    backend = "postgres"

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._pool: Any | None = None

    async def connect(self) -> None:
        if not _ASYNCPG_AVAILABLE:  # pragma: no cover
            raise RuntimeError("asyncpg not installed")
        self._pool = await asyncpg.create_pool(self._database_url, min_size=1, max_size=8)

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()

    async def issue_canonical_user(self, *, phone, full_name, dob, email) -> UUID:
        # canonical_uuid is the DB default gen_random_uuid (random/opaque).
        async with self._pool.acquire() as con:  # type: ignore[union-attr]
            if phone:
                existing = await con.fetchval(
                    "SELECT canonical_uuid FROM pii_vault.users WHERE phone = $1", phone
                )
                if existing:
                    return existing
            row = await con.fetchrow(
                """
                INSERT INTO pii_vault.users (phone, full_name, dob, email)
                VALUES ($1, $2, $3, $4)
                RETURNING canonical_uuid
                """,
                phone, full_name, dob, email,
            )
            return row["canonical_uuid"]

    async def resolve_by_phone(self, phone: str) -> UUID | None:
        async with self._pool.acquire() as con:  # type: ignore[union-attr]
            return await con.fetchval(
                "SELECT canonical_uuid FROM pii_vault.users WHERE phone = $1", phone
            )

    async def age_tier_for(self, canonical_uuid: UUID) -> str:
        async with self._pool.acquire() as con:  # type: ignore[union-attr]
            dob = await con.fetchval(
                "SELECT dob FROM pii_vault.users WHERE canonical_uuid = $1", canonical_uuid
            )
        return _derive_age_tier(dob.isoformat() if dob else None)

    async def active_memberships(self, canonical_uuid, app=None) -> list[dict[str, Any]]:
        query = (
            "SELECT app, role, scope, granted_at, revoked_at "
            "FROM platform.app_memberships "
            "WHERE canonical_uuid = $1 AND revoked_at IS NULL"
        )
        params: list[Any] = [canonical_uuid]
        if app:
            query += " AND app = $2"
            params.append(app)
        async with self._pool.acquire() as con:  # type: ignore[union-attr]
            rows = await con.fetch(query, *params)
            # Fold in active time-bound grants (delegated/temporary/substitute)
            # so the resolver treats them exactly like memberships in-window.
            grant_q = (
                "SELECT app, role, scope, starts_at AS granted_at, "
                "expires_at AS revoked_at FROM platform.access_grants "
                "WHERE grantee = $1 AND revoked_at IS NULL "
                "AND now() BETWEEN starts_at AND expires_at"
            )
            gparams: list[Any] = [canonical_uuid]
            if app:
                grant_q += " AND app = $2"
                gparams.append(app)
            grows = await con.fetch(grant_q, *gparams)
        return [dict(r) for r in rows] + [dict(r) for r in grows]

    async def grant_consent(self, *, canonical_uuid, scope, purpose, age_tier, granted_by) -> dict[str, Any]:
        async with self._pool.acquire() as con:  # type: ignore[union-attr]
            row = await con.fetchrow(
                """
                INSERT INTO platform.consents
                  (canonical_uuid, scope, purpose, age_tier, granted_by)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (canonical_uuid, scope, purpose)
                  WHERE revoked_at IS NULL
                  DO UPDATE SET age_tier = EXCLUDED.age_tier
                RETURNING consent_id, canonical_uuid, scope, purpose, age_tier,
                          granted_by, granted_at, revoked_at
                """,
                canonical_uuid, scope, purpose, age_tier, granted_by,
            )
        return dict(row)

    async def check_consent(self, *, canonical_uuid, scope, purpose) -> dict[str, Any]:
        async with self._pool.acquire() as con:  # type: ignore[union-attr]
            row = await con.fetchrow(
                """
                SELECT consent_id FROM platform.consents
                WHERE canonical_uuid = $1 AND scope = $2 AND purpose = $3
                  AND revoked_at IS NULL
                LIMIT 1
                """,
                canonical_uuid, scope, purpose,
            )
        return {"satisfied": row is not None, "consent_ref": row["consent_id"] if row else None}

    # --- SSO federation (vault) -----------------------------------------
    async def resolve_by_federation(self, *, provider, subject) -> UUID | None:
        async with self._pool.acquire() as con:  # type: ignore[union-attr]
            return await con.fetchval(
                "SELECT canonical_uuid FROM pii_vault.federations "
                "WHERE provider = $1 AND subject = $2",
                provider, subject,
            )

    async def link_federation(self, *, canonical_uuid, provider, subject, email, full_name) -> None:
        async with self._pool.acquire() as con:  # type: ignore[union-attr]
            await con.execute(
                """
                INSERT INTO pii_vault.federations (canonical_uuid, provider, subject, email, full_name)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (provider, subject) DO NOTHING
                """,
                canonical_uuid, provider, subject, email, full_name,
            )

    # --- Devices & session risk -----------------------------------------
    async def register_device(self, *, canonical_uuid, device_fingerprint, label, platform) -> dict[str, Any]:
        async with self._pool.acquire() as con:  # type: ignore[union-attr]
            row = await con.fetchrow(
                """
                INSERT INTO platform.devices
                  (canonical_uuid, fingerprint, label, platform)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (canonical_uuid, fingerprint) WHERE revoked_at IS NULL
                  DO UPDATE SET last_seen_at = now()
                RETURNING device_id, canonical_uuid, label, platform,
                          registered_at, last_seen_at, revoked_at, trusted
                """,
                canonical_uuid, device_fingerprint, label, platform,
            )
        return dict(row)

    async def list_devices(self, canonical_uuid) -> list[dict[str, Any]]:
        async with self._pool.acquire() as con:  # type: ignore[union-attr]
            rows = await con.fetch(
                "SELECT device_id, canonical_uuid, label, platform, registered_at, "
                "last_seen_at, revoked_at, trusted FROM platform.devices "
                "WHERE canonical_uuid = $1 ORDER BY registered_at",
                canonical_uuid,
            )
        return [dict(r) for r in rows]

    async def revoke_device(self, *, canonical_uuid, device_id) -> bool:
        async with self._pool.acquire() as con:  # type: ignore[union-attr]
            res = await con.execute(
                "UPDATE platform.devices SET revoked_at = now() "
                "WHERE device_id = $1 AND canonical_uuid = $2 AND revoked_at IS NULL",
                device_id, canonical_uuid,
            )
        return res.endswith("1")

    async def record_session_risk(self, *, canonical_uuid, session_id, risk, signals, device_id) -> dict[str, Any]:
        async with self._pool.acquire() as con:  # type: ignore[union-attr]
            row = await con.fetchrow(
                """
                INSERT INTO platform.session_risk
                  (session_id, canonical_uuid, risk, signals, device_id)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING session_id, canonical_uuid, risk, signals, device_id, assessed_at
                """,
                session_id, canonical_uuid, risk, signals, device_id,
            )
        return dict(row)

    # --- Access history --------------------------------------------------
    async def record_access(self, *, canonical_uuid, action, outcome, app=None, scope=None,
                            device_id=None, session_id=None, risk=None) -> dict[str, Any]:
        async with self._pool.acquire() as con:  # type: ignore[union-attr]
            row = await con.fetchrow(
                """
                INSERT INTO platform.access_history
                  (canonical_uuid, action, app, scope, outcome, device_id, session_id, risk)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING event_id, canonical_uuid, action, app, scope, outcome,
                          occurred_at, device_id, session_id, risk
                """,
                canonical_uuid, action, app, scope, outcome, device_id, session_id, risk,
            )
        return dict(row)

    async def access_history(self, canonical_uuid, *, limit=100) -> list[dict[str, Any]]:
        async with self._pool.acquire() as con:  # type: ignore[union-attr]
            rows = await con.fetch(
                "SELECT event_id, canonical_uuid, action, app, scope, outcome, "
                "occurred_at, device_id, session_id, risk FROM platform.access_history "
                "WHERE canonical_uuid = $1 ORDER BY occurred_at DESC LIMIT $2",
                canonical_uuid, limit,
            )
        return [dict(r) for r in rows]

    # --- Time-bound access grants ---------------------------------------
    async def create_access_grant(self, *, kind, grantee, granted_by, app, role, scope,
                                  starts_at, expires_at, reason) -> dict[str, Any]:
        async with self._pool.acquire() as con:  # type: ignore[union-attr]
            row = await con.fetchrow(
                """
                INSERT INTO platform.access_grants
                  (kind, grantee, granted_by, app, role, scope, starts_at, expires_at, reason)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING grant_id, kind, grantee, granted_by, app, role, scope,
                          starts_at, expires_at, reason, granted_at, revoked_at
                """,
                kind, grantee, granted_by, app, role, scope, starts_at, expires_at, reason,
            )
        return dict(row)

    async def list_access_grants(self, *, grantee=None, granted_by=None) -> list[dict[str, Any]]:
        query = (
            "SELECT grant_id, kind, grantee, granted_by, app, role, scope, "
            "starts_at, expires_at, reason, granted_at, revoked_at "
            "FROM platform.access_grants WHERE 1=1"
        )
        params: list[Any] = []
        if grantee is not None:
            params.append(grantee)
            query += f" AND grantee = ${len(params)}"
        if granted_by is not None:
            params.append(granted_by)
            query += f" AND granted_by = ${len(params)}"
        query += " ORDER BY granted_at DESC"
        async with self._pool.acquire() as con:  # type: ignore[union-attr]
            rows = await con.fetch(query, *params)
        return [dict(r) for r in rows]

    async def revoke_access_grant(self, *, grant_id) -> bool:
        async with self._pool.acquire() as con:  # type: ignore[union-attr]
            res = await con.execute(
                "UPDATE platform.access_grants SET revoked_at = now() "
                "WHERE grant_id = $1 AND revoked_at IS NULL",
                grant_id,
            )
        return res.endswith("1")


class InMemoryIdentityStore(IdentityStore):
    """Non-durable fallback so the API runs without a database. Clearly labelled.

    Keeps the SAME segregation discipline: PII lives only in ``_vault``; the
    behavioral dicts hold opaque canonical_uuid only.
    """

    backend = "in-memory (degraded — NOT durable; set clss.identity.dev.database_url)"

    def __init__(self) -> None:
        self._vault: dict[UUID, dict[str, Any]] = {}
        self._phone_index: dict[str, UUID] = {}
        # Federation index lives in the vault boundary: (provider, subject) -> uuid.
        self._federation_index: dict[tuple[str, str], UUID] = {}
        self._memberships: list[dict[str, Any]] = []
        self._consents: list[dict[str, Any]] = []
        self._devices: list[dict[str, Any]] = []
        self._sessions: list[dict[str, Any]] = []
        self._access_log: list[dict[str, Any]] = []
        self._grants: list[dict[str, Any]] = []

    async def connect(self) -> None:
        logger.warning("identity store running IN-MEMORY: data is not durable. "
                        "Provide clss.identity.dev.database_url for Postgres.")

    async def close(self) -> None:
        return None

    async def issue_canonical_user(self, *, phone, full_name, dob, email) -> UUID:
        if phone and phone in self._phone_index:
            return self._phone_index[phone]
        cuid = uuid4()  # random/opaque — never derived from PII (INVARIANT 2)
        self._vault[cuid] = {
            "phone": phone, "full_name": full_name, "dob": dob, "email": email,
            "created_at": _now(),
        }
        if phone:
            self._phone_index[phone] = cuid
        return cuid

    async def resolve_by_phone(self, phone: str) -> UUID | None:
        return self._phone_index.get(phone)

    async def age_tier_for(self, canonical_uuid: UUID) -> str:
        rec = self._vault.get(canonical_uuid, {})
        return _derive_age_tier(rec.get("dob"))

    async def active_memberships(self, canonical_uuid, app=None) -> list[dict[str, Any]]:
        out = [
            m for m in self._memberships
            if m["canonical_uuid"] == canonical_uuid and m["revoked_at"] is None
            and (app is None or m["app"] == app)
        ]
        # First-class time-bound grants surface as memberships for the grantee so
        # the resolver and the gateway treat substitute/delegated/temporary access
        # exactly like any other membership — but only inside the active window.
        for g in self._grants:
            if g["grantee"] != canonical_uuid or not _grant_active(g):
                continue
            if app is not None and g["app"] != app:
                continue
            out.append({
                "canonical_uuid": canonical_uuid, "app": g["app"], "role": g["role"],
                "scope": g["scope"], "granted_at": g["starts_at"],
                "revoked_at": g["expires_at"], "grant_id": g["grant_id"],
                "grant_kind": g["kind"],
            })
        return out

    async def grant_consent(self, *, canonical_uuid, scope, purpose, age_tier, granted_by) -> dict[str, Any]:
        for c in self._consents:
            if (c["canonical_uuid"] == canonical_uuid and c["scope"] == scope
                    and c["purpose"] == purpose and c["revoked_at"] is None):
                c["age_tier"] = age_tier
                return c
        rec = {
            "consent_id": uuid4(), "canonical_uuid": canonical_uuid, "scope": scope,
            "purpose": purpose, "age_tier": age_tier, "granted_by": granted_by,
            "granted_at": _now(), "revoked_at": None,
        }
        self._consents.append(rec)
        return rec

    async def check_consent(self, *, canonical_uuid, scope, purpose) -> dict[str, Any]:
        for c in self._consents:
            if (c["canonical_uuid"] == canonical_uuid and c["scope"] == scope
                    and c["purpose"] == purpose and c["revoked_at"] is None):
                return {"satisfied": True, "consent_ref": c["consent_id"]}
        return {"satisfied": False, "consent_ref": None}

    # --- SSO federation (vault) -----------------------------------------
    async def resolve_by_federation(self, *, provider: str, subject: str) -> UUID | None:
        return self._federation_index.get((provider, subject))

    async def link_federation(self, *, canonical_uuid, provider, subject, email, full_name) -> None:
        self._federation_index[(provider, subject)] = canonical_uuid
        rec = self._vault.setdefault(canonical_uuid, {"created_at": _now()})
        # Provider PII stays in the vault; never crosses the boundary.
        rec.setdefault("federations", []).append({"provider": provider, "subject": subject})
        if email and not rec.get("email"):
            rec["email"] = email
        if full_name and not rec.get("full_name"):
            rec["full_name"] = full_name

    # --- Devices & session risk -----------------------------------------
    async def register_device(self, *, canonical_uuid, device_fingerprint, label, platform) -> dict[str, Any]:
        for d in self._devices:
            if (d["canonical_uuid"] == canonical_uuid
                    and d["_fingerprint"] == device_fingerprint and d["revoked_at"] is None):
                d["last_seen_at"] = _now()
                return d
        rec = {
            "device_id": uuid4(), "canonical_uuid": canonical_uuid,
            "_fingerprint": device_fingerprint, "label": label, "platform": platform,
            "registered_at": _now(), "last_seen_at": _now(), "revoked_at": None,
            "trusted": False,
        }
        self._devices.append(rec)
        return rec

    async def list_devices(self, canonical_uuid) -> list[dict[str, Any]]:
        return [d for d in self._devices if d["canonical_uuid"] == canonical_uuid]

    async def revoke_device(self, *, canonical_uuid, device_id) -> bool:
        for d in self._devices:
            if (d["device_id"] == device_id and d["canonical_uuid"] == canonical_uuid
                    and d["revoked_at"] is None):
                d["revoked_at"] = _now()
                return True
        return False

    async def record_session_risk(self, *, canonical_uuid, session_id, risk, signals, device_id) -> dict[str, Any]:
        rec = {
            "session_id": session_id, "canonical_uuid": canonical_uuid, "risk": risk,
            "signals": list(signals), "device_id": device_id, "assessed_at": _now(),
        }
        self._sessions.append(rec)
        return rec

    # --- Access history --------------------------------------------------
    async def record_access(self, *, canonical_uuid, action, outcome, app=None, scope=None,
                            device_id=None, session_id=None, risk=None) -> dict[str, Any]:
        rec = {
            "event_id": uuid4(), "canonical_uuid": canonical_uuid, "action": action,
            "app": app, "scope": scope, "outcome": outcome, "occurred_at": _now(),
            "device_id": device_id, "session_id": session_id, "risk": risk,
        }
        self._access_log.append(rec)
        return rec

    async def access_history(self, canonical_uuid, *, limit=100) -> list[dict[str, Any]]:
        rows = [e for e in self._access_log if e["canonical_uuid"] == canonical_uuid]
        rows.sort(key=lambda e: e["occurred_at"], reverse=True)
        return rows[:limit]

    # --- Time-bound access grants ---------------------------------------
    async def create_access_grant(self, *, kind, grantee, granted_by, app, role, scope,
                                  starts_at, expires_at, reason) -> dict[str, Any]:
        rec = {
            "grant_id": uuid4(), "kind": kind, "grantee": grantee, "granted_by": granted_by,
            "app": app, "role": role, "scope": scope, "starts_at": starts_at,
            "expires_at": expires_at, "reason": reason, "granted_at": _now(),
            "revoked_at": None,
        }
        self._grants.append(rec)
        return rec

    async def list_access_grants(self, *, grantee=None, granted_by=None) -> list[dict[str, Any]]:
        out = []
        for g in self._grants:
            if grantee is not None and g["grantee"] != grantee:
                continue
            if granted_by is not None and g["granted_by"] != granted_by:
                continue
            out.append(g)
        return out

    async def revoke_access_grant(self, *, grant_id) -> bool:
        for g in self._grants:
            if g["grant_id"] == grant_id and g["revoked_at"] is None:
                g["revoked_at"] = _now()
                return True
        return False

    # Test/dev seam: seed a membership without a real grant flow.
    def seed_membership(self, *, canonical_uuid: UUID, app: str, role: str, scope: dict[str, Any]) -> None:
        self._memberships.append({
            "canonical_uuid": canonical_uuid, "app": app, "role": role,
            "scope": scope, "granted_at": _now(), "revoked_at": None,
        })


def build_store(database_url: str | None) -> IdentityStore:
    """Pick the adapter. Postgres when configured and the driver is present;
    otherwise the labelled in-memory fallback."""
    if database_url and _ASYNCPG_AVAILABLE:
        return PostgresIdentityStore(database_url)
    if database_url and not _ASYNCPG_AVAILABLE:  # pragma: no cover
        logger.warning("database_url set but asyncpg unavailable; using in-memory store.")
    return InMemoryIdentityStore()
