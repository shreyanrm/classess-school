"""The immutable audit layer (spine A7).

INVARIANT 9 — AUDIT IS IMMUTABLE. There is ONLY ``record`` (append) and
``query`` (read) here. No update, no delete. The Postgres adapter writes
``platform.audit_log`` whose immutability trigger and INSERT-only grants are the
hard enforcement; this code never issues UPDATE/DELETE. The in-memory adapter
enforces the SAME discipline — its backing list is appended to and never mutated
or removed from, and ``query`` returns copies so a caller cannot reach back in
and edit the ledger.

Every meaningful governance action is recorded with an attributed, timestamped
entry: who, what, on which resource, under which purpose, in which tenant scope
(INVARIANT 10), and whether it was a privileged / break-glass action.

The query layer is read-only and consent-agnostic by design: the audit log is
the record OF access control, not subject behavioral data, so it carries no PII
(actors and resources are opaque refs/labels) and never enters the behavioral
event store.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from .models import AuditQuery, AuditRecord, new_id

logger = logging.getLogger("clss.governance.audit")

try:  # Optional durable backend; absent in the deterministic/test paths.
    import asyncpg  # type: ignore

    _ASYNCPG_AVAILABLE = True
except Exception:  # pragma: no cover
    asyncpg = None  # type: ignore
    _ASYNCPG_AVAILABLE = False


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AuditLog(ABC):
    """Append + read only. No mutation surface exists, by contract."""

    backend: str

    @abstractmethod
    async def record(
        self,
        *,
        actor_uuid: UUID,
        action: str,
        resource: str,
        purpose: str,
        tenant_id: UUID,
        privileged: bool = False,
        detail: dict | None = None,
        occurred_at: datetime | None = None,
    ) -> AuditRecord:
        """Append one immutable audit entry; return the stored record."""

    @abstractmethod
    async def query(self, q: AuditQuery) -> list[AuditRecord]:
        """Read the log. Never mutates it; returns copies."""


def _matches(rec: AuditRecord, q: AuditQuery) -> bool:
    if q.actor_uuid is not None and rec.actor_uuid != q.actor_uuid:
        return False
    if q.action is not None and rec.action != q.action:
        return False
    if q.resource is not None and rec.resource != q.resource:
        return False
    if q.tenant_id is not None and rec.tenant_id != q.tenant_id:
        return False
    if q.privileged_only and not rec.privileged:
        return False
    if q.since is not None and rec.occurred_at < q.since:
        return False
    if q.until is not None and rec.occurred_at > q.until:
        return False
    return True


class InMemoryAuditLog(AuditLog):
    """Append-only in-memory ledger. Clearly labelled, not durable, but enforces
    immutability: the backing list is only appended to, and queries return copies
    so callers cannot reach in and edit recorded history."""

    backend = "in-memory append-only ledger (degraded — set clss.governance.dev.audit_database_url)"

    def __init__(self) -> None:
        self._log: list[AuditRecord] = []

    async def record(
        self,
        *,
        actor_uuid: UUID,
        action: str,
        resource: str,
        purpose: str,
        tenant_id: UUID,
        privileged: bool = False,
        detail: dict | None = None,
        occurred_at: datetime | None = None,
    ) -> AuditRecord:
        now = _now()
        rec = AuditRecord(
            audit_id=new_id(),
            actor_uuid=actor_uuid,
            action=action,
            resource=resource,
            purpose=purpose,
            tenant_id=tenant_id,
            occurred_at=occurred_at or now,
            recorded_at=now,
            privileged=privileged,
            detail=dict(detail or {}),
        )
        # Append only. The list is never mutated or deleted from.
        self._log.append(rec)
        return rec

    async def query(self, q: AuditQuery) -> list[AuditRecord]:
        out = [rec for rec in self._log if _matches(rec, q)]
        out.sort(key=lambda r: r.occurred_at)
        # AuditRecord is frozen, so the references are themselves immutable; the
        # list itself is a fresh copy. The ledger cannot be reordered or trimmed
        # through the returned value.
        return out[: max(0, q.limit)]


class PostgresAuditLog(AuditLog):
    """Durable backend over ``platform.audit_log`` (INSERT-only grants + an
    immutability trigger enforce no UPDATE/DELETE at the database wall)."""

    backend = "postgres (platform.audit_log, immutable: INSERT-only)"

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._pool: Any | None = None

    async def connect(self) -> None:  # pragma: no cover - needs a live DB
        if not _ASYNCPG_AVAILABLE:
            raise RuntimeError("asyncpg not installed")
        self._pool = await asyncpg.create_pool(self._database_url, min_size=1, max_size=8)

    async def close(self) -> None:  # pragma: no cover
        if self._pool is not None:
            await self._pool.close()

    async def record(  # pragma: no cover - needs a live DB
        self, *, actor_uuid, action, resource, purpose, tenant_id,
        privileged=False, detail=None, occurred_at=None,
    ) -> AuditRecord:
        import json

        now = _now()
        occ = occurred_at or now
        async with self._pool.acquire() as con:  # type: ignore[union-attr]
            row = await con.fetchrow(
                """
                INSERT INTO platform.audit_log
                  (actor_uuid, action, resource, purpose, tenant_id,
                   privileged, detail, occurred_at, recorded_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8,$9)
                RETURNING audit_id, occurred_at, recorded_at
                """,
                actor_uuid, action, resource, purpose, tenant_id,
                privileged, json.dumps(detail or {}), occ, now,
            )
        return AuditRecord(
            audit_id=row["audit_id"], actor_uuid=actor_uuid, action=action,
            resource=resource, purpose=purpose, tenant_id=tenant_id,
            occurred_at=row["occurred_at"], recorded_at=row["recorded_at"],
            privileged=privileged, detail=dict(detail or {}),
        )

    async def query(self, q: AuditQuery) -> list[AuditRecord]:  # pragma: no cover
        import json

        clauses: list[str] = []
        args: list[Any] = []

        def add(cond: str, val: Any) -> None:
            args.append(val)
            clauses.append(cond.format(len(args)))

        if q.actor_uuid is not None:
            add("actor_uuid = ${}", q.actor_uuid)
        if q.action is not None:
            add("action = ${}", q.action)
        if q.resource is not None:
            add("resource = ${}", q.resource)
        if q.tenant_id is not None:
            add("tenant_id = ${}", q.tenant_id)
        if q.privileged_only:
            clauses.append("privileged = true")
        if q.since is not None:
            add("occurred_at >= ${}", q.since)
        if q.until is not None:
            add("occurred_at <= ${}", q.until)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        args.append(max(0, q.limit))
        sql = (
            "SELECT * FROM platform.audit_log" + where
            + f" ORDER BY occurred_at ASC LIMIT ${len(args)}"
        )
        async with self._pool.acquire() as con:  # type: ignore[union-attr]
            rows = await con.fetch(sql, *args)
        return [
            AuditRecord(
                audit_id=r["audit_id"], actor_uuid=r["actor_uuid"], action=r["action"],
                resource=r["resource"], purpose=r["purpose"], tenant_id=r["tenant_id"],
                occurred_at=r["occurred_at"], recorded_at=r["recorded_at"],
                privileged=r["privileged"],
                detail=json.loads(r["detail"]) if isinstance(r["detail"], str) else dict(r["detail"] or {}),
            )
            for r in rows
        ]


def build_audit_log(database_url: str | None) -> AuditLog:
    if database_url and _ASYNCPG_AVAILABLE:
        return PostgresAuditLog(database_url)
    if database_url and not _ASYNCPG_AVAILABLE:  # pragma: no cover
        logger.warning("audit_database_url set but asyncpg unavailable; using in-memory ledger.")
    return InMemoryAuditLog()
