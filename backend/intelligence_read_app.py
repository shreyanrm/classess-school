"""The HTTP handler binding for ``POST /v1/intelligence/read`` — the spine's
one-engine, one-truth faucet, served as a real route.

``spine/gateway/app/routing.py`` already maps ``learning.read`` and
``intelligence-views.read`` to ``POST /v1/intelligence/read``, and
``config.capability_targets()`` points the ``intelligence`` upstream at the
in-process mount ``{self_base_url}/internal/intelligence``. The route itself was
glue-pending: nothing actually served it. This module is that binding.

It is a tiny FastAPI sub-app the deployable mounts under ``/internal/intelligence``
so the gateway's ``_forward`` reaches ``/internal/intelligence/v1/intelligence/read``.
The handler REUSES :mod:`backend.intelligence_views` (which already loads the ONE
engine under a unique alias and replays the seeded event store through it) — no
engine logic is re-implemented here; this only exposes it over HTTP.

LAWS honoured:
  * The gateway is the wall: this mount lives under ``/internal`` and is only
    reachable via the gateway forward (which already ran authn -> RBAC -> ABAC ->
    consent -> audit) or the in-process door. It performs no auth of its own — it
    is BEHIND the wall, not a second wall — and holds no secret.
  * ONE engine, one truth: the body comes straight from the Python intelligence
    engine via ``intelligence_views.read``.
  * Degrade cleanly: engine unavailable -> 503 (the surface falls back to its
    in-browser engine port); unknown/malformed view -> 422; never a crash.
  * Import-safe: importing this module performs no I/O and reads no secret value.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import Body, FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from . import intelligence_views

logger = logging.getLogger("clss.backend.intelligence_read")

app = FastAPI(
    title="Classess Intelligence Read (spine faucet)",
    version="0.1.0",
    description=(
        "Serves POST /v1/intelligence/read by replaying the immutable event "
        "store through the ONE intelligence engine. Mounted behind the wall."
    ),
)


@app.get("/healthz", tags=["meta"])
async def healthz() -> dict:
    return {
        "status": "ok",
        "service": "intelligence-read",
        "engine": "available" if intelligence_views.available() else "degraded",
    }


@app.post("/v1/intelligence/read", tags=["intelligence"])
async def intelligence_read(
    body: Optional[dict[str, Any]] = Body(default=None),
) -> JSONResponse:
    """Compute one governed intelligence view (mastery / gaps / recommendations /
    class-insights) by replaying the event store through the ONE engine.

    The request body carries the ``view`` selector and an optional
    ``subject_uuid`` (the gateway forwarded it from the wall-admitted call). The
    response is the governed view as the TOP-LEVEL body so a surface's shape guard
    trusts it. Engine degraded -> 503 (fall back to the in-browser port); unknown
    view -> 422.
    """
    if not intelligence_views.available():
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "reason": "intelligence_engine_unavailable"},
        )
    payload = body or {}
    try:
        view_body = intelligence_views.read(
            view=payload.get("view"),
            subject_uuid=payload.get("subject_uuid"),
        )
    except intelligence_views.IntelligenceUnavailable:
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "reason": "intelligence_engine_unavailable"},
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=422,
            content={"error": "unknown_view", "detail": str(exc)},
        )
    return JSONResponse(status_code=200, content=jsonable_encoder(view_body))
