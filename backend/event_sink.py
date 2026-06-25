"""The in-process EVENT-STORE sink wiring — the deployable's append seam.

The architecture's seam: modules emit attributed events UP into the immutable
event store; no app bulk-reads the canonical store. In the single deployable the
event store runs in-process (mounted under ``/internal/event-store``); this
module is the thin seam that lets the deployable's own runtime (the workflow
proactive loop, the intelligence emitter) APPEND through that same store — the
in-process equivalent of an authenticated append through the gateway/event-store.

It REUSES the event-store's own ``build_event_store`` adapter (loaded under its
unique alias), so the append honours INVARIANT 5 (append-only, no mutation) and
degrades to the in-memory append-only log when no ``clss.eventstore.dev.database_url``
is wired — identical write contract with or without a DB.

LAWS honoured:
  * Import-safe: importing this module performs no I/O and reads no secret value;
    the store is built lazily on first append.
  * Degrade cleanly: event-store package absent / store unbuildable -> the append
    reports ``persisted: False`` rather than crashing the loop.
  * Append-only: there is only an append path here; no update, no delete.
  * No PII: the caller (the workflow builders) already strips PII; this seam adds
    nothing beyond the opaque canonical ref.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from . import loader

logger = logging.getLogger("clss.backend.event_sink")

_store: Any | None = None
_connected = False

# ONE dedicated background event loop for ALL store I/O. A real Postgres store
# (asyncpg pool) is bound to the loop it was created on, so every append + the
# one-time connect MUST run on the SAME loop — a per-call ``asyncio.run`` (a new
# loop each time) breaks the pool. We own a single long-lived loop on a daemon
# thread and marshal every coroutine onto it. The in-memory store works on this
# loop too, so there is one code path with or without a DB.
_loop: asyncio.AbstractEventLoop | None = None
_loop_lock = threading.Lock()      # guards the one-time loop-thread start
_connect_lock = threading.Lock()   # guards the one-time store.connect()


def _background_loop() -> asyncio.AbstractEventLoop:
    """Return the process's single dedicated store loop, starting its daemon
    thread on first use. Idempotent + thread-safe."""
    global _loop
    if _loop is not None:
        return _loop
    with _loop_lock:
        if _loop is not None:  # pragma: no cover - double-checked locking
            return _loop
        loop = asyncio.new_event_loop()

        def _serve() -> None:
            asyncio.set_event_loop(loop)
            loop.run_forever()

        threading.Thread(target=_serve, name="clss-event-sink-loop", daemon=True).start()
        _loop = loop
    return _loop


def _to_uuid(v: Any) -> UUID:
    try:
        return UUID(str(v))
    except Exception:
        return uuid4()


def _build_store() -> Any | None:
    """Build the event-store adapter once, reusing the event-store's own
    ``build_event_store`` + settings (loaded under its unique alias). Degrades to
    None when the package is unavailable."""
    global _store
    if _store is not None:
        return _store
    pkg = loader.load_spine_app("event-store")  # imports {alias}.main (and the pkg)
    if pkg is None:
        logger.warning("event-store unavailable; workflow/intelligence events will not persist")
        return None
    alias = loader._alias_for("svc", "event-store")
    try:
        store_mod = __import__(f"{alias}.store", fromlist=["*"])
        config_mod = __import__(f"{alias}.config", fromlist=["*"])
        settings = config_mod.get_settings()
        _store = store_mod.build_event_store(settings.database_url)
    except Exception as exc:  # pragma: no cover - defensive degrade path
        logger.warning("failed to build event store (degrading): %s", exc)
        return None
    return _store


def _run(coro: Any) -> Any:
    """Drive a store coroutine to completion on the ONE dedicated background loop.

    The capability door / workflow handler runs INSIDE FastAPI's request loop, so
    ``asyncio.run`` would raise (a loop is already running). And a fresh loop per
    call breaks a real asyncpg pool (it is bound to one loop). So we submit every
    coroutine to the single long-lived background loop via ``run_coroutine_
    threadsafe`` and block on the result — connect + append + read all share that
    loop, which is what a real Postgres pool requires. The in-memory store works
    on the same path (its append never blocks), so there is one code path."""
    loop = _background_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()


def available() -> bool:
    return _build_store() is not None


def append_emit_input(emit_input: dict[str, Any]) -> dict[str, Any]:
    """Append one event given an event-store ``EmitEventInput`` dict
    (``{app, canonical_uuid, purpose, consent_ref, occurred_at, type, payload}``)
    — the exact shape ``WorkflowEvent.as_emit_input`` / the intelligence
    ``build_envelope`` produce.

    Returns ``{type, persisted, event_id?}``. ``persisted`` is True only when a
    real store accepted it; on any degrade it is False and the event is NOT lost
    to the caller's result (the caller still returns the built event)."""
    global _connected
    store = _build_store()
    if store is None:
        return {"type": emit_input.get("type"), "persisted": False, "reason": "event_store_unavailable"}
    occurred = emit_input.get("occurred_at")
    if isinstance(occurred, str):
        occurred_dt = datetime.fromisoformat(occurred)
    elif isinstance(occurred, datetime):
        occurred_dt = occurred
    else:
        occurred_dt = datetime.now(timezone.utc)
    try:
        if not _connected:
            # Connect ONCE on the shared loop (a real pool binds to it). Use a
            # SEPARATE lock from the loop-start lock: _run() acquires _loop_lock
            # to start the loop thread, so guarding connect with _loop_lock too
            # would self-deadlock (threading.Lock is non-reentrant).
            with _connect_lock:
                if not _connected:
                    _run(store.connect())
                    _connected = True
        stored = _run(
            store.append(
                canonical_uuid=_to_uuid(emit_input.get("canonical_uuid")),
                app=str(emit_input.get("app", "workflow")),
                type=str(emit_input.get("type")),
                purpose=str(emit_input.get("purpose", "intervention")),
                consent_ref=_to_uuid(emit_input.get("consent_ref")),
                payload=dict(emit_input.get("payload") or {}),
                occurred_at=occurred_dt,
            )
        )
        return {
            "type": stored.get("type"),
            "persisted": True,
            "event_id": str(stored.get("event_id")),
        }
    except Exception as exc:  # degrade cleanly, never break the loop
        logger.warning("event append degraded: %s", exc)
        return {"type": emit_input.get("type"), "persisted": False, "reason": f"{type(exc).__name__}"}


def store_backend() -> Optional[str]:
    store = _build_store()
    return getattr(store, "backend", None) if store is not None else None
