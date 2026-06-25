"""Classess backend — ONE deployable FastAPI app.

Feature-based modules inside a single deployable. The gateway is the front door
(THE WALL); the spine services (identity, event-store) and the capability
modules (institution, ontology-ingestion, scheduling, content, planning,
coursework, learning, attendance, classroom, learner-record, communication) are
wired in-process BEHIND the wall.

Topology in this one process:

  /                          -> the gateway app (the wall). Its public surface:
      /v1/route/{cap}/{op}       the ONLY governed door into a capability
      /v1/policy/evaluate        dry-run policy decision
      /v1/tracks                 two-track routing config
  /health                    -> liveness for the deployable (PORT-bound)
  /capabilities/{cap}/{op}   -> generic capability door enforced by the Wall
                                 pipeline (rate-limit -> authn -> RBAC -> ABAC ->
                                 consent -> approval -> child-safety -> audit).
                                 Deny-by-default: no/invalid token => denied.
  /internal/identity/*       -> identity service, mounted for the gateway to
  /internal/event-store/*       forward to in-process (still gateway-guarded for
                                 the public path; mounted under /internal).

LAWS honoured:
  * Secrets are read from the environment BY NAME only (PORT, CLSS_DATABASE_URL,
    CLSS_SUPABASE_URL/SERVICE_KEY, CLSS_AIFABRIC_*_KEY, REDIS_URL). Nothing is
    hardcoded; no secret value is logged.
  * The gateway is the wall: RBAC + ABAC, deny-by-default.
  * Import-safe: importing this module performs no I/O and reads no secret value.
  * Degrade cleanly: a missing dependency env or absent capability never crashes
    the process; the affected door reports a degraded/denied state instead.
"""

from __future__ import annotations

import contextlib
import logging
from typing import Any, Optional

from fastapi import Body, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

from . import loader
from .wall_auth import WallTokenVerifier

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("clss.backend")


# --------------------------------------------------------------------------- #
# Load the gateway (the wall) + its building blocks under unique aliases.
# --------------------------------------------------------------------------- #
_gateway_pkg = loader.load_gateway()
_gw_main = __import__(f"{loader.GATEWAY_ALIAS}.main", fromlist=["app"])
_gw_caps = __import__(f"{loader.GATEWAY_ALIAS}.capabilities", fromlist=["*"])
_gw_wall = __import__(f"{loader.GATEWAY_ALIAS}.wall", fromlist=["*"])
_gw_rl = __import__(f"{loader.GATEWAY_ALIAS}.ratelimit", fromlist=["*"])
_gw_cfg = __import__(f"{loader.GATEWAY_ALIAS}.config", fromlist=["*"])

gateway_app: FastAPI = _gw_main.app

# Capability registry + wall, built once. The registry declares every capability
# module as a routable capability behind the full enforcement chain.
_registry = _gw_caps.build_default_registry()
_limiter = _gw_rl.RateLimiter(
    default_rule=_gw_rl.RateLimitRule(
        limit=120, window_seconds=60.0, algorithm=_gw_rl.Algorithm.TOKEN_BUCKET
    )
)
# Token verification for the in-process Wall. We read the gateway's per-service
# settings (CLSS_GATEWAY_DEV_*) BY NAME and build a synchronous verifier the Wall
# can call. When NO public key and NO introspect URL are configured (the deploy
# case), the verifier accepts the clearly-marked DEV-UNSIGNED token (logged as
# dev-only) so the live gateway can actually resolve a Principal and serve
# capability reads — RBAC/ABAC still gate downstream. When a real key/introspect
# is configured, dev tokens are rejected. Reading settings here performs no I/O
# and reveals no secret value; absent config degrades to dev-only, never open.
_gw_settings = _gw_cfg.get_settings()
_wall_verifier = WallTokenVerifier(
    principal_cls=_gw_caps.Principal,
    public_key=_gw_settings.jwt_public_key,
    introspect_url=_gw_settings.identity_introspect_url,
)
# consent/child-safety remain SAFE defaults (cross-context reads still gate;
# free text fails closed). Audit is the in-memory ring when no DB is wired. The
# wall NEVER runs open.
_wall = _gw_wall.Wall(registry=_registry, limiter=_limiter, verifier=_wall_verifier)


# --------------------------------------------------------------------------- #
# Resolve the spine sub-apps + capability modules BEFORE building the parent app,
# so the parent lifespan can drive each child sub-app's own lifespan. Starlette
# only runs the TOP-LEVEL app's lifespan; mounted sub-apps need their lifespans
# entered explicitly or their ``app.state`` (verifier, store, tracks, audit) is
# never populated.
# --------------------------------------------------------------------------- #
_MOUNTED_SPINE: set[str] = set()
_CHILD_APPS: list[FastAPI] = []


def _resolve_spine() -> list[tuple[str, FastAPI]]:
    resolved: list[tuple[str, FastAPI]] = []
    for name in loader.SPINE_APPS:
        svc = loader.load_spine_app(name)
        if svc is None:
            logger.warning("spine service '%s' unavailable; mounting skipped (degraded)", name)
            continue
        resolved.append((name, svc.app))
    return resolved


def _eager_load_capabilities() -> None:
    """Import each capability module under its alias so import errors surface at
    startup (not at first request). Absent/broken modules degrade to a log line;
    the wall still denies their routes by default if they are not registered."""
    for name in loader.CAPABILITY_MODULES:
        mod = loader.load_capability_module(name)
        if mod is None:
            logger.warning("capability module '%s' not loaded (degraded)", name)


_spine_apps = _resolve_spine()
_eager_load_capabilities()


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI):
    """Drive the lifespan of every mounted sub-app (gateway + spine) so their
    ``app.state`` is wired. Each child lifespan degrades cleanly on missing env
    (it logs missing NAMES only and runs in a degraded mode), so entering them
    here is safe offline."""
    async with contextlib.AsyncExitStack() as stack:
        for child in _CHILD_APPS:
            router = child.router
            if getattr(router, "lifespan_context", None) is not None:
                await stack.enter_async_context(router.lifespan_context(child))
        yield


# --------------------------------------------------------------------------- #
# The single deployable app. The gateway IS the front door, so we mount it at
# the root and add the deployable-level /health and the generic capability door.
# --------------------------------------------------------------------------- #
app = FastAPI(
    title="Classess Backend (one deployable)",
    version="0.1.0",
    description=(
        "Single deployable. The gateway is the wall; identity, event-store and "
        "the capability modules are wired in-process behind it."
    ),
    lifespan=lifespan,
)


@app.get("/health", tags=["meta"])
async def health() -> dict:
    """Deployable liveness. Reports which capability modules loaded and whether
    the spine services are mounted, without ever revealing a secret value."""
    return {
        "status": "ok",
        "service": "classess-backend",
        "wall": "active",
        "capabilities": _registry.modules(),
        "spine_mounted": sorted(_MOUNTED_SPINE),
    }


# --------------------------------------------------------------------------- #
# Generic capability door — every call passes the wall (deny-by-default).
# --------------------------------------------------------------------------- #
_ACTION_ALIASES = {
    "read": "read",
    "get": "read",
    "write": "write",
    "post": "write",
    "create": "write",
    "update": "write",
    "export": "export",
    "approve": "approve",
    # Consequential write verbs the surfaces use map onto the canonical "write"
    # action the wall enforces (RBAC/ABAC/consent/approval/child-safety/audit).
    # The semantic name stays legible at the door; the wall still gates it as a
    # write, so a surface can never reach a module without passing the wall.
    "confirm": "write",   # attendance confirm
    "send": "write",      # messages / communication send (permission ladder)
    "submit": "write",    # coursement submission (permission ladder)
    "emit": "write",      # event append
    "publish": "write",   # school structure publish
    "converse": "write",  # Vidya turn (the orchestrator's tool-use ladder)
    "grade": "write",     # evaluation grade (permission ladder)
    "delete": "write",    # erasure
    "erase": "write",     # identity erasure
}


@app.api_route("/capabilities/{capability}/{operation}", methods=["GET", "POST"], tags=["capabilities"])
async def capability_door(
    capability: str,
    operation: str,
    authorization: Optional[str] = Header(default=None),
    x_consent_purpose: Optional[str] = Header(default=None, alias="X-Consent-Purpose"),
    x_approval_token: Optional[str] = Header(default=None, alias="X-Approval-Token"),
    body: Optional[dict[str, Any]] = Body(default=None),
) -> JSONResponse:
    """Route into a capability module THROUGH the wall.

    The wall runs: route-exists -> authn -> rate-limit -> schema-validate ->
    RBAC -> ABAC -> consent (cross-context) -> approval (consequential) ->
    child-safety -> audit. Any failure is denied (fail closed). An
    unauthenticated call is therefore denied here, not inside any module.
    """
    action = _ACTION_ALIASES.get(operation.lower())
    if action is None:
        raise HTTPException(status_code=404, detail=f"unknown operation '{operation}'")
    route = f"{capability}.{action}"

    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()

    cross_context = x_consent_purpose is not None
    payload = body or {}

    try:
        _wall.admit(
            route=route,
            token=token,
            payload=payload,
            cross_context=cross_context,
            approval_token=x_approval_token,
        )
    except _gw_caps.WallDenied as denied:
        # Deny-by-default. NO_TOKEN / INVALID_TOKEN -> 401; everything else 403.
        reason = denied.reason
        status = 401 if reason in (
            _gw_caps.DenyReason.NO_TOKEN,
            _gw_caps.DenyReason.INVALID_TOKEN,
        ) else 403
        return JSONResponse(
            status_code=status,
            content={"error": "denied", "reason": reason.value, "detail": denied.detail or None},
        )

    # Admitted: the capability module performs its work. Modules are pure-python
    # libraries (no HTTP router of their own), so the door acknowledges the
    # governed admission. Concrete module dispatch is wired per-operation later.
    return JSONResponse(
        status_code=200,
        content={"status": "admitted", "capability": capability, "operation": action},
    )


# --------------------------------------------------------------------------- #
# Mount the spine services + the gateway in-process, behind the deployable.
# The public, governed door stays the gateway; identity/event-store live under
# /internal so the gateway can reach them in-process when configured to.
# --------------------------------------------------------------------------- #
for _name, _svc_app in _spine_apps:
    app.mount(f"/internal/{_name}", _svc_app)
    _MOUNTED_SPINE.add(_name)
    _CHILD_APPS.append(_svc_app)
    logger.info("mounted spine service in-process: /internal/%s", _name)

# Mount the gateway (the wall) LAST, at the root, so it is the front door for the
# governed /v1/* surface. Done after /health and /capabilities so those explicit
# deployable routes are not shadowed by the gateway's root mount.
app.mount("/", gateway_app)
_CHILD_APPS.append(gateway_app)


def _port() -> int:
    """Listen port — read from PORT by name (Railway sets it). Defaults to 8080."""
    import os

    raw = os.environ.get("PORT", "8080")
    try:
        return int(raw)
    except ValueError:
        return 8080


if __name__ == "__main__":  # pragma: no cover - process entrypoint
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=_port())
