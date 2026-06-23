"""Event Store service — immutable append-only write-path + governed read.

Mirrors contracts/src/openapi/event-store.ts:
  POST /v1/event-store/events            -> emit (append-only; INVARIANT 5)
  GET  /v1/event-store/events            -> governed, consent+purpose-gated read
  GET  /v1/event-store/events/{event_id} -> governed single-event read

There is deliberately NO update and NO delete endpoint. Reads ALWAYS go through
the governed path: a read without a satisfied consent + purpose check returns an
empty set (or 404 for a single event), never the rows.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status

from .config import EventStoreSettings, get_settings
from .models import (
    EmitEventInput,
    EventEnvelope,
    EventTypeName,
    Purpose,
)
from .store import EventStore, build_event_store
from .verify import TokenVerifier, VerificationError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("clss.eventstore")

# Defense-in-depth check: the payload must never carry top-level PII keys. This
# mirrors the DB CHECK intent and is a second wall against accidental leakage.
_FORBIDDEN_PAYLOAD_KEYS = {"phone", "name", "full_name", "dob", "email", "address", "ssn", "aadhaar"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    missing = settings.degraded_reasons()
    if missing:
        logger.warning("event-store starting DEGRADED. Missing config (names only): %s", ", ".join(missing))
    store = build_event_store(settings.database_url)
    await store.connect()
    verifier = TokenVerifier(
        public_key=settings.jwt_public_key,
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        algorithm=settings.jwt_algorithm,
    )
    app.state.store = store
    app.state.verifier = verifier
    app.state.settings = settings
    logger.info("event-store backend: %s", store.backend)
    try:
        yield
    finally:
        await store.close()


app = FastAPI(
    title="Classess Event Store",
    version="0.1.0",
    description=(
        "Append-only, immutable, attributed event store. Emit events and read "
        "them back through governed, consent-scoped views only. No mutation, no "
        "deletion."
    ),
    lifespan=lifespan,
)


def get_store() -> EventStore:
    return app.state.store


def get_verifier() -> TokenVerifier:
    return app.state.verifier


@app.get("/healthz", tags=["meta"])
async def healthz() -> dict:
    return {"status": "ok", "service": "event-store", "store": get_store().backend}


# ---------------------------------------------------------------------------
# Emit — append-only (INVARIANT 5)
# ---------------------------------------------------------------------------
@app.post("/v1/event-store/events", response_model=EventEnvelope, status_code=201, tags=["emit"])
async def emit_event(
    body: EmitEventInput,
    authorization: str | None = Header(default=None),
    store: EventStore = Depends(get_store),
    verifier: TokenVerifier = Depends(get_verifier),
) -> EventEnvelope:
    _verify(verifier, authorization)
    _reject_pii(body.payload)
    occurred_at = body.occurred_at or datetime.now(timezone.utc)
    stored = await store.append(
        canonical_uuid=body.canonical_uuid,
        app=body.app,
        type=body.type,
        purpose=body.purpose,
        consent_ref=body.consent_ref,
        payload=body.payload,
        occurred_at=occurred_at,
    )
    return EventEnvelope(**stored)


# ---------------------------------------------------------------------------
# Governed reads (INVARIANT 6)
# ---------------------------------------------------------------------------
@app.get("/v1/event-store/events", response_model=list[EventEnvelope], tags=["read"])
async def read_events(
    purpose: Purpose = Query(description="Purpose asserted for this read (INVARIANT 6)."),
    canonical_uuid: UUID | None = Query(default=None, description="Opaque subject filter."),
    type: EventTypeName | None = Query(default=None),
    since: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    authorization: str | None = Header(default=None),
    store: EventStore = Depends(get_store),
    verifier: TokenVerifier = Depends(get_verifier),
) -> list[EventEnvelope]:
    claims = _verify(verifier, authorization)
    # If no explicit subject is asserted, the caller may only read their own
    # events (defense in depth; the gateway also scope-checks).
    subject = canonical_uuid or UUID(claims["canonical_uuid"])
    rows = await store.read_events(
        canonical_uuid=subject, purpose=purpose, type=type, since=since, limit=limit
    )
    return [EventEnvelope(**r) for r in rows]


@app.get("/v1/event-store/events/{event_id}", response_model=EventEnvelope, tags=["read"])
async def read_event(
    event_id: UUID,
    purpose: Purpose = Query(description="Purpose asserted for this read (INVARIANT 6)."),
    authorization: str | None = Header(default=None),
    store: EventStore = Depends(get_store),
    verifier: TokenVerifier = Depends(get_verifier),
) -> EventEnvelope:
    _verify(verifier, authorization)
    row = await store.read_event(event_id=event_id, purpose=purpose)
    if row is None:
        # 404 not 403: do not distinguish "not found" from "not visible".
        raise HTTPException(status_code=404, detail="not found or not visible to caller")
    return EventEnvelope(**row)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _verify(verifier: TokenVerifier, authorization: str | None) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        return verifier.verify(token)
    except VerificationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def _reject_pii(payload: dict) -> None:
    leaked = _FORBIDDEN_PAYLOAD_KEYS & set(payload.keys())
    if leaked:
        # INVARIANT 1: no PII in the behavioral store. Refuse with a 422 that
        # names the offending keys (not their values).
        raise HTTPException(
            status_code=422,
            detail=f"payload may not carry PII keys: {sorted(leaked)}",
        )
