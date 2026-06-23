"""Immutable audit emitter (INVARIANT 9).

Every gateway call — allowed or denied — is recorded. The audit log is
append-only (db/migrations 0005; INSERT-only grants). Records carry the opaque
actor canonical_uuid, the action (capability.operation), the decision, the ABAC
resource scope evaluated, the policy reasons, and a request id. NO PII, NO
secrets, NO token contents are ever written.

Sinks:
  - PostgresAuditSink: writes platform.audit_log via asyncpg.
  - LoggerAuditSink: degraded fallback that logs structured JSON (no PII) when
    no database is configured, so the wall never silently drops an audit.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

logger = logging.getLogger("clss.gateway.audit")

try:
    import asyncpg  # type: ignore

    _ASYNCPG_AVAILABLE = True
except Exception:  # pragma: no cover
    asyncpg = None  # type: ignore
    _ASYNCPG_AVAILABLE = False


@dataclass
class AuditRecord:
    action: str                       # capability.operation
    decision: str                     # allow | deny
    actor_canonical_uuid: UUID | None = None
    app: str | None = None
    resource_scope: dict[str, Any] | None = None
    reasons: list[str] = field(default_factory=list)
    break_glass: bool = False
    request_id: UUID = field(default_factory=uuid4)
    recorded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_safe_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["actor_canonical_uuid"] = str(self.actor_canonical_uuid) if self.actor_canonical_uuid else None
        d["request_id"] = str(self.request_id)
        d["recorded_at"] = self.recorded_at.isoformat()
        return d


class AuditSink(ABC):
    backend: str

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def close(self) -> None: ...

    @abstractmethod
    async def emit(self, record: AuditRecord) -> None: ...


class PostgresAuditSink(AuditSink):
    backend = "postgres (platform.audit_log)"

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._pool: Any | None = None

    async def connect(self) -> None:
        if not _ASYNCPG_AVAILABLE:  # pragma: no cover
            raise RuntimeError("asyncpg not installed")
        self._pool = await asyncpg.create_pool(self._database_url, min_size=1, max_size=4)

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()

    async def emit(self, record: AuditRecord) -> None:
        async with self._pool.acquire() as con:  # type: ignore[union-attr]
            await con.execute(
                """
                INSERT INTO platform.audit_log
                  (audit_id, actor_canonical_uuid, app, action, decision,
                   resource_scope, reasons, break_glass, request_id, recorded_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                record.request_id,  # audit_id (unique per call)
                record.actor_canonical_uuid,
                record.app,
                record.action,
                record.decision,
                json.dumps(record.resource_scope) if record.resource_scope is not None else None,
                json.dumps(record.reasons),
                record.break_glass,
                record.request_id,
                record.recorded_at,
            )


class LoggerAuditSink(AuditSink):
    backend = "logger (degraded — set clss.gateway.dev.database_url for durable audit)"

    async def connect(self) -> None:
        logger.warning("audit sink is LOGGER-only: records are not durably stored. "
                       "Set clss.gateway.dev.database_url.")

    async def close(self) -> None:
        return None

    async def emit(self, record: AuditRecord) -> None:
        logger.info("AUDIT %s", json.dumps(record.to_safe_dict(), separators=(",", ":")))


def build_audit_sink(database_url: str | None) -> AuditSink:
    if database_url and _ASYNCPG_AVAILABLE:
        return PostgresAuditSink(database_url)
    return LoggerAuditSink()
