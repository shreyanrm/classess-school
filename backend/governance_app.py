"""The GOVERNANCE control plane binding (GAP#3/#5/#7) — toggles, break-glass,
policy version and emergency-disable, each PERSISTED + immutably audited.

The governance & safety package (spine A7) is a pure-python library. This module
MOUNTS it in the deployable behind the wall: the AI-control toggle (enable /
emergency-disable), break-glass open, a policy-version record, and the
audit-trail READ. Every consequential governance action does TWO durable things:

  1. records an IMMUTABLE audit entry through the governance ``AuditLog`` (the
     append-only, INSERT-only ``platform.audit_log`` when wired; the in-memory
     append-only ledger when degraded). This is what the audit-trail READ
     (``do_audit_trail``) queries — append + query only, no mutation surface.
  2. emits a clean attributed event to the behavioural EVENT STORE via the
     ``event_sink`` seam (``governance.toggled`` / ``governance.breakglass`` /
     ``governance.policy_version``), so the action is also a persisted,
     consent-stamped event in the immutable store.

The toggle / break-glass / policy-version verbs are CONSEQUENTIAL: the wall
forces an X-Approval-Token on the EXECUTE rung they route onto, so a governance
write can never auto-fire. ``do_audit_trail`` is a READ.

LAWS: import-safe (no I/O at import); degrade cleanly (governance lib absent ->
routes report unavailable, never crash); append-only persistence; no PII (opaque
actor / tenant refs and capability labels only).
"""

from __future__ import annotations

import importlib
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from . import event_sink, loader

logger = logging.getLogger("clss.backend.governance")

# Load the governance control plane under its unique alias (degrades to None).
# The package __init__ does not eagerly import its submodules, so reach them via
# the alias explicitly (their internal relative imports keep working).
_gov = loader.load_governance()
if _gov is not None:
    try:
        _gov_audit = importlib.import_module(f"{loader.GOVERNANCE_ALIAS}.audit")
        _gov_control = importlib.import_module(f"{loader.GOVERNANCE_ALIAS}.control_centre")
        _gov_breakglass = importlib.import_module(f"{loader.GOVERNANCE_ALIAS}.breakglass")
        _gov_models = importlib.import_module(f"{loader.GOVERNANCE_ALIAS}.models")
        _gov_config = importlib.import_module(f"{loader.GOVERNANCE_ALIAS}.config")
    except Exception as exc:  # pragma: no cover - degrade cleanly
        logger.warning("governance submodules unavailable (degrading): %s", exc)
        _gov = None

# Singletons for the process: one immutable audit log + one control centre + one
# break-glass service. The audit log is the durable store of record for the
# governance audit-trail READ; it is in-memory append-only when no
# clss.governance.dev.audit_database_url is wired (identical query contract).
_AUDIT: Any | None = None
_CONTROL: Any | None = None
_BREAKGLASS: Any | None = None

# A stable default tenant scope for the degraded single-deployable path (INVARIANT
# 10 wants a tenant scope on every governance action; the surface supplies the
# real one). Opaque, PII-free.
_DEFAULT_TENANT = UUID("70000000-0000-4000-8000-0000000000a7")


def available() -> bool:
    return _gov is not None


def _u(v: Any, default: UUID | None = None) -> UUID:
    try:
        return UUID(str(v))
    except Exception:
        return default or uuid4()


def _audit_log() -> Any:
    global _AUDIT
    if _AUDIT is None:
        try:
            settings = _gov_config.get_settings()
            audit_db = getattr(settings, "audit_database_url", None)
        except Exception:  # pragma: no cover - settings degrade
            audit_db = None
        _AUDIT = _gov_audit.build_audit_log(audit_db)
    return _AUDIT


def _control() -> Any:
    global _CONTROL
    if _CONTROL is None:
        _CONTROL = _gov_control.ControlCentre(_audit_log())
    return _CONTROL


def _breakglass() -> Any:
    global _BREAKGLASS
    if _BREAKGLASS is None:
        _BREAKGLASS = _gov_breakglass.BreakGlassService(_audit_log())
    return _BREAKGLASS


def _emit_event(type_: str, *, actor: UUID, payload: dict[str, Any], consent_ref: Any) -> dict[str, Any]:
    """Emit an attributed governance event into the behavioural event store seam.
    Returns ``{type, persisted, event_id?}`` (persisted False on degrade)."""
    return event_sink.append_emit_input(
        {
            "app": "governance",
            "canonical_uuid": str(actor),
            "purpose": "governance",
            "consent_ref": str(consent_ref or uuid4()),
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "type": type_,
            "payload": payload,
        }
    )


# --------------------------------------------------------------------------- #
# The governance steps as plain (status, dict) functions. The capability door
# (backend/dispatch.py) calls these AFTER the wall admits; the EXECUTE-rung verbs
# (toggle / breakglass / policy version) are already approval-gated upstream.
# --------------------------------------------------------------------------- #
def do_toggle(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """AI-control toggle: emergency-disable or re-enable a capability. PERSISTS
    the new state, records an immutable privileged audit entry, AND emits a
    ``governance.toggled`` event to the event store."""
    if not available():
        return 503, {"status": "degraded", "reason": "governance_runtime_unavailable"}
    capability = str(payload.get("capability") or "").strip()
    if not capability:
        return 422, {"error": "capability_required"}
    enable = bool(payload.get("enabled", payload.get("enable", False)))
    actor = _u(payload.get("actor_uuid") or payload.get("subject_uuid") or payload.get("decided_by"))
    tenant = _u(payload.get("tenant_id"), _DEFAULT_TENANT)
    reason = str(payload.get("reason") or "").strip()
    try:
        cc = _control()
        if enable:
            state = event_sink._run(cc.enable(capability=capability, actor_uuid=actor, tenant_id=tenant))
            action = "enable"
        else:
            if not reason:
                return 422, {"error": "reason_required", "detail": "emergency-disable requires a reason"}
            state = event_sink._run(
                cc.emergency_disable(capability=capability, reason=reason, actor_uuid=actor, tenant_id=tenant)
            )
            action = "emergency_disable"
        event = _emit_event(
            "governance.toggled",
            actor=actor,
            payload={"capability": capability, "enabled": state.enabled, "action": action,
                     "reason": state.disabled_reason},
            consent_ref=payload.get("consent_ref"),
        )
        return 200, {
            "capability": capability,
            "enabled": state.enabled,
            "action": action,
            "disabled_reason": state.disabled_reason,
            "audited": True,
            "event": event,
        }
    except ValueError as exc:
        return 422, {"error": "toggle_refused", "detail": str(exc)}
    except Exception as exc:  # pragma: no cover - degrade cleanly
        logger.warning("governance toggle degraded: %s", exc)
        return 422, {"error": "toggle_failed", "detail": f"{type(exc).__name__}"}


def do_breakglass(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Break-glass: open privileged access. REQUIRES a reason (refused without),
    records an immutable privileged audit entry, AND emits a
    ``governance.breakglass`` event to the event store."""
    if not available():
        return 503, {"status": "degraded", "reason": "governance_runtime_unavailable"}
    capability = str(payload.get("capability") or "").strip()
    if not capability:
        return 422, {"error": "capability_required"}
    actor = _u(payload.get("actor_uuid") or payload.get("subject_uuid") or payload.get("decided_by"))
    tenant = _u(payload.get("tenant_id"), _DEFAULT_TENANT)
    reason = str(payload.get("reason") or "")
    approved_by = payload.get("approved_by")
    try:
        bg = _breakglass()
        grant = event_sink._run(
            bg.open(
                actor_uuid=actor,
                capability=capability,
                reason=reason,
                tenant_id=tenant,
                approved_by=_u(approved_by) if approved_by else None,
            )
        )
        event = _emit_event(
            "governance.breakglass",
            actor=actor,
            payload={"capability": capability, "grant_id": str(grant.grant_id),
                     "expires_at": grant.expires_at.isoformat()},
            consent_ref=payload.get("consent_ref"),
        )
        return 200, {
            "grant_id": str(grant.grant_id),
            "capability": capability,
            "expires_at": grant.expires_at.isoformat(),
            "audited": True,
            "event": event,
        }
    except Exception as exc:
        # ReasonRequiredError / ApprovalRequiredError are real refusals — surface.
        logger.warning("break-glass refused/degraded: %s", exc)
        return 422, {"error": "breakglass_refused", "detail": str(exc)}


def do_policy_version(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Record a POLICY VERSION change immutably. The institution module owns the
    inheritance/lock resolver; here the governance plane records THAT a versioned
    policy change happened, immutably audited, and emits a
    ``governance.policy_version`` event to the event store."""
    if not available():
        return 503, {"status": "degraded", "reason": "governance_runtime_unavailable"}
    key = str(payload.get("key") or payload.get("policy_key") or "").strip()
    if not key:
        return 422, {"error": "policy_key_required"}
    node_id = str(payload.get("node_id") or payload.get("scope") or "root")
    version = int(payload.get("version", 1))
    actor = _u(payload.get("actor_uuid") or payload.get("subject_uuid") or payload.get("decided_by"))
    tenant = _u(payload.get("tenant_id"), _DEFAULT_TENANT)
    locked = bool(payload.get("locked", False))
    try:
        log = _audit_log()
        rec = event_sink._run(
            log.record(
                actor_uuid=actor,
                action="policy.version",
                resource=f"{node_id}:{key}",
                purpose="governance",
                tenant_id=tenant,
                privileged=True,
                detail={"key": key, "node_id": node_id, "version": version, "locked": locked},
            )
        )
        event = _emit_event(
            "governance.policy_version",
            actor=actor,
            payload={"key": key, "node_id": node_id, "version": version, "locked": locked},
            consent_ref=payload.get("consent_ref"),
        )
        return 200, {
            "audit_id": str(rec.audit_id),
            "key": key,
            "node_id": node_id,
            "version": version,
            "locked": locked,
            "audited": True,
            "event": event,
        }
    except Exception as exc:  # pragma: no cover - degrade cleanly
        logger.warning("policy-version degraded: %s", exc)
        return 422, {"error": "policy_version_failed", "detail": f"{type(exc).__name__}"}


def do_audit_trail(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """The audit-trail READ — query the immutable governance audit log. Read-only;
    never mutates the ledger (returns copies)."""
    if not available():
        return 503, {"status": "degraded", "reason": "governance_runtime_unavailable"}
    try:
        models = _gov_models
        actor = payload.get("actor_uuid")
        resource = payload.get("resource")
        q = models.AuditQuery(
            actor_uuid=_u(actor) if actor else None,
            action=payload.get("action"),
            resource=str(resource) if resource else None,
            tenant_id=_u(payload.get("tenant_id")) if payload.get("tenant_id") else None,
            privileged_only=bool(payload.get("privileged_only", False)),
            limit=int(payload.get("limit", 100)),
        )
        records = event_sink._run(_audit_log().query(q))
        return 200, {
            "count": len(records),
            "records": [
                {
                    "audit_id": str(r.audit_id),
                    "actor_uuid": str(r.actor_uuid),
                    "action": r.action,
                    "resource": r.resource,
                    "purpose": r.purpose,
                    "privileged": r.privileged,
                    "occurred_at": r.occurred_at.isoformat(),
                    "detail": dict(r.detail),
                }
                for r in records
            ],
        }
    except Exception as exc:  # pragma: no cover - degrade cleanly
        logger.warning("audit-trail read degraded: %s", exc)
        return 422, {"error": "audit_trail_failed", "detail": f"{type(exc).__name__}"}
