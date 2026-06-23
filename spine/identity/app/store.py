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
        return [dict(r) for r in rows]

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


class InMemoryIdentityStore(IdentityStore):
    """Non-durable fallback so the API runs without a database. Clearly labelled.

    Keeps the SAME segregation discipline: PII lives only in ``_vault``; the
    behavioral dicts hold opaque canonical_uuid only.
    """

    backend = "in-memory (degraded — NOT durable; set clss.identity.dev.database_url)"

    def __init__(self) -> None:
        self._vault: dict[UUID, dict[str, Any]] = {}
        self._phone_index: dict[str, UUID] = {}
        self._memberships: list[dict[str, Any]] = []
        self._consents: list[dict[str, Any]] = []

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
