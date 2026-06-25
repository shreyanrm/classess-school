"""The workflow runtime binding — recommend -> approve -> execute, served.

The workflow engine (spine A5) is a pure-python library (no FastAPI app of its
own). This module MOUNTS it in the deployable: a thin HTTP sub-app, served under
``/internal/workflow``, that drives the proactive loop's three governed rungs and
PERSISTS the four loop events to the event store (the seam).

  POST /v1/workflow/recommend  -> mint a Recommendation from a cohort-weakness
                                  signal; emit ``recommendation.created``.
  POST /v1/workflow/approve    -> record the human decision in the ledger (the
                                  ApprovalControl gate); emit ``recommendation.
                                  actioned`` and, for a clearing decision,
                                  ``approval.given``.
  POST /v1/workflow/execute    -> run the GATED execute; on a cleared
                                  consequential action emit ``action.executed``.

It REUSES the workflow library's builders + loop functions (loaded under a unique
alias) and the deployable's ``event_sink`` for the append — it re-implements no
judgment and writes the store through the one seam. The in-process
``InMemoryApprovalLedger`` is the runtime mirror; the durable store of record is
the event store (the four persisted events).

The gateway forwards learning/intelligence-views/workflow recommend/approve/
execute here (config.capability_targets() -> /internal/workflow). Each rung is
already wall-gated upstream (EXECUTE is consequential -> the wall forced the
X-Approval-Token); this runtime additionally enforces the ladder (execute refuses
without a recorded human approval — INVARIANT 8).

LAWS: import-safe (no I/O at import); degrade cleanly (workflow lib absent -> the
routes report unavailable, never crash); append-only persistence via the seam.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from fastapi import Body, FastAPI
from fastapi.responses import JSONResponse

from . import event_sink, loader

logger = logging.getLogger("clss.backend.workflow")

# Load the workflow runtime under its unique alias (degrades to None when absent).
_wf = loader.load_workflow()
# The package re-exports most of the loop, but the step-4 ``approve`` lives in the
# ``loop`` submodule and is not in the package __all__; reach it directly via the
# alias (no edit to the workflow subtree). None when the runtime is unavailable.
_wf_loop = (
    __import__(f"{loader.WORKFLOW_ALIAS}.loop", fromlist=["approve"]) if _wf is not None else None
)

app = FastAPI(
    title="Classess Workflow (proactive loop runtime)",
    version="0.1.0",
    description=(
        "Serves the proactive loop's recommend -> approve -> execute rungs and "
        "persists the four loop events to the event store. Mounted behind the wall."
    ),
)

# The runtime mirror of the approval state machine. The durable store of record is
# the event store (the persisted approval.given / action.executed events). One
# ledger for the process is sufficient for the in-process loop; it never holds PII.
_LEDGER: Any | None = None
# Recommendations minted this process, by id — so approve/execute can rebuild the
# object the loop steps operate on without the surface round-tripping the whole
# (provenanced) recommendation. PII-free (opaque refs only).
_RECS: dict[str, Any] = {}


def available() -> bool:
    return _wf is not None


def _ledger() -> Any:
    global _LEDGER
    if _LEDGER is None:
        _LEDGER = _wf.InMemoryApprovalLedger()
    return _LEDGER


def _u(v: Any) -> UUID:
    try:
        return UUID(str(v))
    except Exception:
        return uuid4()


def _persist(event: Any, *, purpose: str, consent_ref: str) -> dict[str, Any]:
    """Append one WorkflowEvent through the event-store seam (degrades cleanly)."""
    emit_input = event.as_emit_input(purpose=purpose, consent_ref=consent_ref)
    return event_sink.append_emit_input(emit_input)


def _resolve_rec(rec_id: str, payload: dict[str, Any]) -> Any | None:
    """Resolve the Recommendation under decision by its STABLE id — the durability
    seam (GAP#2). Tries the process mirror first; on a miss it REHYDRATES an
    engine-derived recommendation by re-minting it deterministically from the
    SAME stable id (the engine view + ``build_recommendation`` are pure, so the
    rebuilt object is identical). This is why an engine-derived id surfaced by a
    recommend can be approved/executed in a LATER request without a 404 — the rec
    is never lost to transient process state; it is always re-derivable."""
    rec = _RECS.get(rec_id)
    if rec is not None:
        return rec
    if not rec_id:
        return None
    # Rehydrate: re-mint the recommendation from its stable id. ``do_recommend``
    # folds the engine view in (engine-derived id -> same provenance) and caches
    # it back into ``_RECS``, so a subsequent approve/execute resolves the object.
    seed = dict(payload)
    seed["recommendation_id"] = rec_id
    status, _ = do_recommend(seed)
    if status == 200:
        return _RECS.get(rec_id)
    return None


@app.get("/healthz", tags=["meta"])
async def healthz() -> dict:
    return {
        "status": "ok",
        "service": "workflow",
        "runtime": "available" if available() else "degraded",
        "event_store": event_sink.store_backend() or "unavailable",
    }


# ---------------------------------------------------------------------------
# The loop steps as plain functions returning (status, dict). Both the HTTP
# routes (the gateway-forward path) and the deployable capability door (the
# in-process dispatch path) call these, so the loop has ONE implementation.
# ---------------------------------------------------------------------------
def _engine_seed_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """If the recommend was asked to come FROM the engine (``from_engine`` set, or
    a ``recommendation_id`` that matches an engine-derived recommendation), fold
    the engine view's fields (stable id, topic, gap, learner count) INTO the
    payload so the minted Recommendation carries the engine's stable id and
    provenance — recommendations come from intelligence_views, not a mock
    (GAP#2). A no-op when the engine is unavailable or the request is not
    engine-derived."""
    try:
        from . import intelligence_views
    except Exception:  # pragma: no cover - defensive
        return payload
    if not intelligence_views.available():
        return payload
    rid = str(payload.get("recommendation_id") or "").strip()
    view: dict[str, Any] | None = None
    if rid:
        view = intelligence_views.recommendation_by_id(rid)
    elif payload.get("from_engine"):
        feed = intelligence_views.recommendations()
        view = feed[0] if feed else None
    if view is None:
        return payload
    merged = dict(payload)
    merged.setdefault("recommendation_id", view["recommendation_id"])
    merged.setdefault("gap_type", view.get("gap_type", "prerequisite"))
    merged.setdefault("topic_label", view.get("topic_id", "the current topic"))
    merged.setdefault("learner_count", view.get("learner_count", 0))
    merged["engine_derived"] = True
    return merged


def do_recommend(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    if not available():
        return 503, {"status": "degraded", "reason": "workflow_runtime_unavailable"}
    try:
        # GAP#2: recommendations come from the ENGINE (intelligence_views), with a
        # STABLE id, so recommend -> approve -> execute reference the same object.
        payload = _engine_seed_payload(payload)
        evidence_ids = payload.get("evidence_event_ids") or [str(uuid4()), str(uuid4())]
        evidence = [
            _wf.EvidenceRef(event_id=_u(eid), summary=str(payload.get("evidence_summary", "attributed evidence")))
            for eid in evidence_ids
        ]
        rec_id = _u(payload.get("recommendation_id")) if payload.get("recommendation_id") else uuid4()
        gap_type = str(payload.get("gap_type", "prerequisite"))
        topic_label = str(payload.get("topic_label", "the current topic"))
        cohort_label = str(payload.get("cohort_label", "Class 10-B"))
        owner_role = str(payload.get("owner_role", "teacher"))
        owner_ref = _u(payload.get("owner_ref") or payload.get("subject_uuid"))
        confidence = float(payload.get("confidence", 0.8))

        # The ladder stage is DERIVED from the action's effect, never passed in.
        # A consequential effect verb (send/publish/...) classifies the
        # recommendation to execute_with_permission so the full loop reaches an
        # action.executed; otherwise it lands at prepare (draft support material).
        effect_verb = str(payload.get("effect_verb", "prepare")).strip().lower()
        if effect_verb in _wf.CONSEQUENTIAL_VERBS:
            action = _wf.ActionDescriptor(
                kind=str(payload.get("action_kind", f"{effect_verb}_support")),
                effect_verb=effect_verb,
                targets_external=bool(payload.get("targets_external", False)),
                description=str(payload.get("suggested_action", "")),
            )
            rec = _wf.build_recommendation(
                evidence_summary=str(
                    payload.get("evidence_summary",
                                f"{cohort_label} shows a {gap_type} gap on {topic_label}.")
                ),
                evidence_refs=evidence,
                confidence=confidence,
                owner_role=owner_role,
                owner_ref=owner_ref,
                suggested_action=str(payload.get(
                    "suggested_action",
                    f"{effect_verb.capitalize()} targeted support for {cohort_label} on {topic_label}.")),
                action=action,
                consequence_of_ignoring=str(payload.get(
                    "consequence_of_ignoring",
                    f"The {gap_type} gap on {topic_label} is likely to compound for {cohort_label}.")),
                why_am_i_seeing_this=str(payload.get(
                    "why_am_i_seeing_this",
                    f"Repeated evidence across {cohort_label} points to a {gap_type} gap on {topic_label}.")),
                recommendation_id=rec_id,
            )
        else:
            signal = _wf.CohortWeaknessSignal(
                cohort_label=cohort_label,
                topic_label=topic_label,
                gap_type=gap_type,
                confidence=confidence,
                evidence=evidence,
                owner_role=owner_role,
                owner_ref=owner_ref,
                learner_count=int(payload.get("learner_count", 0)),
            )
            rec = _wf.build_cohort_weakness_recommendation(signal, recommendation_id=rec_id)
        _RECS[str(rec.id)] = rec

        purpose = str(payload.get("purpose", "intervention"))
        consent_ref = str(payload.get("consent_ref") or uuid4())
        created = _wf.recommendation_created(rec)
        persisted = _persist(created, purpose=purpose, consent_ref=consent_ref)
        return 200, {
            "recommendation_id": str(rec.id),
            "ladder_stage": rec.ladder_stage,
            "is_consequential": rec.is_consequential,
            "confidence_band": rec.confidence_band,
            "why_am_i_seeing_this": rec.why_am_i_seeing_this,
            "suggested_action": rec.suggested_action,
            "event": persisted,
        }
    except Exception as exc:
        logger.warning("recommend degraded: %s", exc)
        return 422, {"error": "recommend_failed", "detail": str(exc)}


def do_approve(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    if not available():
        return 503, {"status": "degraded", "reason": "workflow_runtime_unavailable"}
    rec_id = str(payload.get("recommendation_id") or "").strip()
    rec = _resolve_rec(rec_id, payload)
    if rec is None:
        return 404, {"error": "unknown_recommendation", "recommendation_id": rec_id}
    try:
        decision_kind = str(payload.get("decision", "approve")).strip()
        decision = _wf.ApprovalDecision(
            recommendation_id=rec.id,
            decision=decision_kind,
            decided_by=_u(payload.get("decided_by") or payload.get("subject_uuid")),
            decided_at=datetime.now(timezone.utc),
            adjustment=payload.get("adjustment"),
            note=payload.get("note"),
        )
        ledger = _ledger()
        state = _wf_loop.approve(rec, ledger, decision=decision)

        purpose = str(payload.get("purpose", "intervention"))
        consent_ref = str(payload.get("consent_ref") or uuid4())

        events: list[dict[str, Any]] = []
        # recommendation.actioned — always (records who decided + how).
        actioned = _wf.recommendation_actioned(decision)
        events.append(_persist(actioned, purpose=purpose, consent_ref=consent_ref))
        # approval.given — only for a CLEARING decision (approve / adjust).
        cleared = decision_kind in ("approve", "adjust")
        if cleared:
            given = _wf.approval_given(decision, resulting_state=state)
            events.append(_persist(given, purpose=purpose, consent_ref=consent_ref))
        return 200, {
            "recommendation_id": rec_id,
            "decision": decision_kind,
            "state": state.value if hasattr(state, "value") else str(state),
            "cleared": cleared,
            "events": events,
        }
    except Exception as exc:
        logger.warning("approve degraded: %s", exc)
        return 422, {"error": "approve_failed", "detail": str(exc)}


def do_execute(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    if not available():
        return 503, {"status": "degraded", "reason": "workflow_runtime_unavailable"}
    rec_id = str(payload.get("recommendation_id") or "").strip()
    rec = _resolve_rec(rec_id, payload)
    if rec is None:
        return 404, {"error": "unknown_recommendation", "recommendation_id": rec_id}
    try:
        ledger = _ledger()
        capability = payload.get("capability")
        result = _wf.execute(rec, ledger, capability=capability)

        purpose = str(payload.get("purpose", "intervention"))
        consent_ref = str(payload.get("consent_ref") or uuid4())

        events: list[dict[str, Any]] = []
        if result.cleared:
            # action.executed — only a CLEARED execution yields an event.
            executed = _wf.action_executed(result, owner_ref=rec.owner.ref)
            events.append(_persist(executed, purpose=purpose, consent_ref=consent_ref))
        return 200, {
            "recommendation_id": rec_id,
            "cleared": result.cleared,
            "performed": result.performed,
            "stage": result.stage.value if hasattr(result.stage, "value") else str(result.stage),
            "reason": result.reason,
            "capability": result.capability,
            "events": events,
        }
    except Exception as exc:
        logger.warning("execute degraded: %s", exc)
        return 422, {"error": "execute_failed", "detail": str(exc)}


# ---------------------------------------------------------------------------
# The HTTP routes — thin wrappers over the loop steps (the gateway-forward path).
# ---------------------------------------------------------------------------
@app.post("/v1/workflow/recommend", tags=["workflow"])
async def recommend(body: Optional[dict[str, Any]] = Body(default=None)) -> JSONResponse:
    status, content = do_recommend(body or {})
    return JSONResponse(status_code=status, content=content)


@app.post("/v1/workflow/approve", tags=["workflow"])
async def approve(body: Optional[dict[str, Any]] = Body(default=None)) -> JSONResponse:
    status, content = do_approve(body or {})
    return JSONResponse(status_code=status, content=content)


@app.post("/v1/workflow/execute", tags=["workflow"])
async def execute(body: Optional[dict[str, Any]] = Body(default=None)) -> JSONResponse:
    status, content = do_execute(body or {})
    return JSONResponse(status_code=status, content=content)
