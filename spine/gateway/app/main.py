"""The gateway — THE WALL. FastAPI app.

Mirrors contracts/src/openapi/gateway.ts:
  POST /v1/route/{capability}/{operation}  -> governed call into a capability
  POST /v1/policy/evaluate                  -> dry-run policy decision

Every routed call passes the same sequence (INVARIANT 3):
  1. verify the identity token (deny by default if absent/invalid)
  2. resolve the operation in the route map (unknown => deny)
  3. evaluate RBAC + ABAC against resolved memberships (deny by default)
  4. for purpose-gated reads, require the X-Consent-Purpose assertion
  5. WRITE an immutable audit record (allow or deny) — INVARIANT 9
  6. only on allow: forward to the upstream capability and return its response

INVARIANT 11: Track 1 / Track 2 routing config is exposed (separately) at
/v1/tracks and lives in two distinct config sections. Track 2 is a reserved
slot, filled later, no re-architecture.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import Body, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from .audit import AuditRecord, build_audit_sink
from .config import get_settings
from .models import PolicyDecision, PolicyEvaluateRequest, VerifiedIdentity
from .policy import PolicyEngine
from .routing import lookup
from .verify import TokenVerifier, VerificationError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("clss.gateway")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    missing = settings.degraded_reasons()
    if missing:
        logger.warning("gateway starting DEGRADED. Missing config (names only): %s", ", ".join(missing))
    verifier = TokenVerifier(
        public_key=settings.jwt_public_key,
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        algorithm=settings.jwt_algorithm,
        introspect_url=settings.identity_introspect_url,
    )
    audit = build_audit_sink(settings.database_url)
    await audit.connect()
    app.state.settings = settings
    app.state.verifier = verifier
    app.state.audit = audit
    app.state.policy = PolicyEngine.baseline()
    app.state.targets = settings.capability_targets()
    app.state.tracks = settings.tracks()
    logger.info("gateway audit sink: %s", audit.backend)
    try:
        yield
    finally:
        await audit.close()


app = FastAPI(
    title="Classess Gateway",
    version="0.1.0",
    description=(
        "The single wall. Token verification, RBAC + ABAC enforcement, schema "
        "validation, immutable audit, and routing. No capability is reachable "
        "except through here."
    ),
    lifespan=lifespan,
)


@app.get("/healthz", tags=["meta"])
async def healthz() -> dict:
    return {"status": "ok", "service": "gateway", "audit": app.state.audit.backend}


@app.get("/v1/tracks", tags=["routing"])
async def tracks() -> dict:
    """Expose the two-track routing config (INVARIANT 11), kept structurally
    separate. Track 2 is a reserved slot, filled later."""
    return app.state.tracks.model_dump()


# ---------------------------------------------------------------------------
# Policy dry-run (pre-check / explainability)
# ---------------------------------------------------------------------------
@app.post("/v1/policy/evaluate", response_model=PolicyDecision, tags=["policy"])
async def policy_evaluate(
    req: PolicyEvaluateRequest,
    authorization: str | None = Header(default=None),
) -> PolicyDecision:
    identity = await _verify(authorization)
    decision = app.state.policy.evaluate(
        identity=identity,
        capability=req.capability,
        operation=req.operation,
        resource_scope=req.resource_scope,
        purpose=req.purpose,
    )
    await app.state.audit.emit(AuditRecord(
        action=f"{req.capability}.{req.operation}",
        decision=decision.decision,
        actor_canonical_uuid=identity.canonical_uuid,
        app=identity.app,
        resource_scope={"scope": req.resource_scope} if req.resource_scope else None,
        reasons=decision.reasons + ["dry-run (policy/evaluate)"],
    ))
    return decision


# ---------------------------------------------------------------------------
# The governed routing entrypoint — the only way into a capability.
# ---------------------------------------------------------------------------
@app.post("/v1/route/{capability}/{operation}", tags=["routing"])
async def gateway_route(
    capability: str,
    operation: str,
    request: Request,
    authorization: str | None = Header(default=None),
    x_consent_purpose: str | None = Header(default=None, alias="X-Consent-Purpose"),
    body: dict[str, Any] | None = Body(default=None),
) -> JSONResponse:
    # 1. Verify token (deny by default).
    identity = await _verify(authorization)

    # 2. Resolve the operation. Unknown => not routable.
    route = lookup(capability, operation)
    if route is None:
        await _audit_deny(identity, capability, operation, x_consent_purpose,
                          ["operation not in route map (not routable)"])
        raise HTTPException(status_code=403, detail=f"operation {capability}.{operation} is not routable")

    # 4. Purpose assertion for cross-context reads (INVARIANT 6).
    if route.purpose_required and not x_consent_purpose:
        await _audit_deny(identity, capability, operation, x_consent_purpose,
                          ["X-Consent-Purpose required for a cross-context read"])
        raise HTTPException(status_code=403, detail="X-Consent-Purpose header required for this read")

    resource_scope = _resource_scope(request, body)

    # 3. RBAC + ABAC (deny by default).
    decision = app.state.policy.evaluate(
        identity=identity,
        capability=capability,
        operation=operation,
        resource_scope=resource_scope,
        purpose=x_consent_purpose,
    )

    # 5. Audit every outcome (INVARIANT 9).
    await app.state.audit.emit(AuditRecord(
        action=f"{capability}.{operation}",
        decision=decision.decision,
        actor_canonical_uuid=identity.canonical_uuid,
        app=identity.app,
        resource_scope={"scope": resource_scope} if resource_scope else None,
        reasons=decision.reasons,
    ))
    if decision.decision == "deny":
        raise HTTPException(status_code=403, detail={"error": "policy_denied", "reasons": decision.reasons})

    # 6. Forward to the upstream capability.
    return await _forward(capability, route, request, body, authorization, x_consent_purpose)


# ---------------------------------------------------------------------------
# Wall helpers
# ---------------------------------------------------------------------------
async def _verify(authorization: str | None) -> VerifiedIdentity:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        return await app.state.verifier.verify(token)
    except VerificationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def _resource_scope(request: Request, body: dict[str, Any] | None) -> str | None:
    # ABAC resource scope is taken from an explicit query/body attribute. Prefer
    # an explicit institution/scope hint; fall back to a canonical_uuid subject.
    q = request.query_params
    for key in ("resource_scope", "scope", "institution_id"):
        if key in q:
            return q[key]
    if body:
        for key in ("resource_scope", "scope", "institution_id"):
            if key in body:
                val = body[key]
                return val if isinstance(val, str) else __import__("json").dumps(val, sort_keys=True)
    return None


async def _forward(
    capability: str,
    route,
    request: Request,
    body: dict[str, Any] | None,
    authorization: str | None,
    purpose: str | None,
) -> JSONResponse:
    target = app.state.targets.get(capability)
    if target is None or not target.base_url:
        env_name = target.base_url_env if target else f"clss.gateway.dev.{capability}_base_url"
        # Degraded: upstream not configured. Name the env var; do not crash.
        return JSONResponse(
            status_code=503,
            content={
                "error": "upstream_unconfigured",
                "detail": f"set {env_name} to enable routing to {capability}",
            },
        )

    path = route.path
    if "{event_id}" in path:
        event_id = request.query_params.get("event_id") or (body or {}).get("event_id")
        if not event_id:
            raise HTTPException(status_code=422, detail="event_id required")
        path = path.replace("{event_id}", str(event_id))

    url = target.base_url.rstrip("/") + path
    headers = {"Authorization": authorization or ""}
    if purpose:
        headers["X-Consent-Purpose"] = purpose
    # Forwarded reads carry the purpose as a query param too (event-store reads).
    params = dict(request.query_params)
    if purpose:
        params.setdefault("purpose", purpose)

    async with httpx.AsyncClient(timeout=15.0) as client:
        if route.method == "GET":
            resp = await client.get(url, headers=headers, params=params)
        else:
            resp = await client.request(route.method, url, headers=headers, params=params, json=body)

    try:
        content = resp.json()
    except Exception:
        content = {"raw": resp.text}
    return JSONResponse(status_code=resp.status_code, content=content)


async def _audit_deny(identity, capability, operation, purpose, reasons) -> None:
    await app.state.audit.emit(AuditRecord(
        action=f"{capability}.{operation}",
        decision="deny",
        actor_canonical_uuid=identity.canonical_uuid,
        app=identity.app,
        reasons=reasons,
    ))
