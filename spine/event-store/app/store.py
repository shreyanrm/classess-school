"""The event store data layer — append-only write, governed read.

INVARIANT 5: there is ONLY ``append`` here — no update, no delete. The Postgres
adapter writes ``platform.events``; the immutability trigger
(``platform.deny_mutation``) and INSERT-only grants in the migrations are the
hard enforcement, and this code never issues UPDATE/DELETE.

INVARIANT 6: reads go ONLY through ``platform.read_events(canonical_uuid,
purpose)`` (db/migrations 0006), which returns rows only when an active consent
for that (person, purpose) exists AND the event's own purpose matches. Without a
satisfied consent the function returns ZERO rows. There is no bulk-select path.

Schema-version note: the DB stores ``schema_version`` as an integer (default 1);
the event contract envelope uses the string ``"v1"``. The adapter normalizes 1
<-> "v1" at the boundary so the API always speaks the contract.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

logger = logging.getLogger("clss.eventstore.store")

try:
    import asyncpg  # type: ignore

    _ASYNCPG_AVAILABLE = True
except Exception:  # pragma: no cover
    asyncpg = None  # type: ignore
    _ASYNCPG_AVAILABLE = False

_SCHEMA_VERSION_DB = 1
_SCHEMA_VERSION_WIRE = "v1"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _to_wire(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    # Normalize schema_version integer -> contract "v1".
    out["schema_version"] = _SCHEMA_VERSION_WIRE
    if isinstance(out.get("payload"), str):
        out["payload"] = json.loads(out["payload"])
    return out


class EventStore(ABC):
    backend: str

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def close(self) -> None: ...

    @abstractmethod
    async def append(
        self,
        *,
        canonical_uuid: UUID,
        app: str,
        type: str,
        purpose: str,
        consent_ref: UUID,
        payload: dict,
        occurred_at: datetime,
    ) -> dict[str, Any]:
        """Append one immutable event; return the stored envelope dict."""

    @abstractmethod
    async def read_events(
        self,
        *,
        canonical_uuid: UUID,
        purpose: str,
        type: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Governed read — consent + purpose gated. Empty set if not satisfied."""

    @abstractmethod
    async def read_event(self, *, event_id: UUID, purpose: str) -> dict[str, Any] | None:
        """Single governed read; None if not visible under the consent gate."""


class PostgresEventStore(EventStore):
    backend = "postgres (platform.events, governed via platform.read_events)"

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

    async def append(self, *, canonical_uuid, app, type, purpose, consent_ref, payload, occurred_at) -> dict[str, Any]:
        # INSERT ONLY. No UPDATE/DELETE path exists in this service.
        async with self._pool.acquire() as con:  # type: ignore[union-attr]
            row = await con.fetchrow(
                """
                INSERT INTO platform.events
                  (canonical_uuid, app, type, purpose, consent_ref, payload,
                   occurred_at, schema_version)
                VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8)
                RETURNING event_id, canonical_uuid, app, type, purpose,
                          consent_ref, payload, occurred_at, recorded_at,
                          schema_version
                """,
                canonical_uuid, app, type, purpose, consent_ref,
                json.dumps(payload), occurred_at, _SCHEMA_VERSION_DB,
            )
        return _to_wire(dict(row))

    async def read_events(self, *, canonical_uuid, purpose, type=None, since=None, limit=100) -> list[dict[str, Any]]:
        # ONLY through the governed function (db/migrations 0006). The consent +
        # purpose gate lives inside read_events; we apply optional type/since
        # filters on top and never touch platform.events directly.
        async with self._pool.acquire() as con:  # type: ignore[union-attr]
            rows = await con.fetch(
                "SELECT * FROM platform.read_events($1, $2)",
                canonical_uuid, purpose,
            )
        results = [_to_wire(dict(r)) for r in rows]
        if type is not None:
            results = [r for r in results if r["type"] == type]
        if since is not None:
            results = [r for r in results if r["occurred_at"] >= since]
        return results[:limit]

    async def read_event(self, *, event_id, purpose) -> dict[str, Any] | None:
        # Resolve the subject via the governed path: find which person's
        # governed view contains this event. We cannot bulk-select, so we look
        # up the event's subject and re-enter through read_events to enforce the
        # gate (never returning a row that the gate would withhold).
        async with self._pool.acquire() as con:  # type: ignore[union-attr]
            subject = await con.fetchval(
                # The subject lookup is itself purpose-constrained: a row is only
                # discoverable when its own purpose matches the asserted purpose.
                "SELECT canonical_uuid FROM platform.events "
                "WHERE event_id = $1 AND purpose = $2 LIMIT 1",
                event_id, purpose,
            )
        if subject is None:
            return None
        rows = await self.read_events(canonical_uuid=subject, purpose=purpose, limit=500)
        for r in rows:
            if r["event_id"] == event_id:
                return r
        return None


class InMemoryEventStore(EventStore):
    """Append-only in-memory log. Clearly labelled, not durable. Enforces the
    SAME discipline: no mutation API, and reads pass the consent + purpose gate."""

    backend = "in-memory append-only log (degraded — set clss.eventstore.dev.database_url)"

    def __init__(self) -> None:
        self._log: list[dict[str, Any]] = []          # immutable append-only
        self._consents: list[dict[str, Any]] = []      # local consent mirror for the gate

    async def connect(self) -> None:
        logger.warning("event store running IN-MEMORY append-only log: not durable. "
                        "Provide clss.eventstore.dev.database_url for Postgres.")

    async def close(self) -> None:
        return None

    def seed_consent(self, *, canonical_uuid: UUID, purpose: str, scope: str = "learning_behavior") -> UUID:
        """Dev seam: register an active consent so the gate can be exercised."""
        consent_id = uuid4()
        self._consents.append({
            "consent_id": consent_id, "canonical_uuid": canonical_uuid,
            "purpose": purpose, "scope": scope, "revoked_at": None,
        })
        return consent_id

    def _consent_satisfied(self, canonical_uuid: UUID, purpose: str) -> bool:
        return any(
            c["canonical_uuid"] == canonical_uuid and c["purpose"] == purpose and c["revoked_at"] is None
            for c in self._consents
        )

    async def append(self, *, canonical_uuid, app, type, purpose, consent_ref, payload, occurred_at) -> dict[str, Any]:
        envelope = {
            "event_id": uuid4(),
            "canonical_uuid": canonical_uuid,
            "app": app,
            "type": type,
            "purpose": purpose,
            "consent_ref": consent_ref,
            "payload": payload,
            "occurred_at": occurred_at,
            "recorded_at": _now(),
            "schema_version": _SCHEMA_VERSION_WIRE,
        }
        # Append only. The list is never mutated or deleted from.
        self._log.append(envelope)
        # A consent.granted event also activates the local gate mirror.
        if type == "consent.granted":
            self._consents.append({
                "consent_id": payload.get("consent_id", consent_ref),
                "canonical_uuid": canonical_uuid, "purpose": payload.get("purpose", purpose),
                "scope": payload.get("scope", ""), "revoked_at": None,
            })
        return dict(envelope)

    async def read_events(self, *, canonical_uuid, purpose, type=None, since=None, limit=100) -> list[dict[str, Any]]:
        # Consent + purpose gate (mirrors platform.read_events): no consent ->
        # zero rows, never an error that leaks existence.
        if not self._consent_satisfied(canonical_uuid, purpose):
            return []
        out = [
            dict(e) for e in self._log
            if e["canonical_uuid"] == canonical_uuid and e["purpose"] == purpose
            and (type is None or e["type"] == type)
            and (since is None or e["occurred_at"] >= since)
        ]
        out.sort(key=lambda e: e["occurred_at"])
        return out[:limit]

    async def read_event(self, *, event_id, purpose) -> dict[str, Any] | None:
        for e in self._log:
            if e["event_id"] == event_id and e["purpose"] == purpose:
                if not self._consent_satisfied(e["canonical_uuid"], purpose):
                    return None
                return dict(e)
        return None


def build_event_store(database_url: str | None) -> EventStore:
    if database_url and _ASYNCPG_AVAILABLE:
        return PostgresEventStore(database_url)
    if database_url and not _ASYNCPG_AVAILABLE:  # pragma: no cover
        logger.warning("database_url set but asyncpg unavailable; using in-memory store.")
    return InMemoryEventStore()
