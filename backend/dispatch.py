"""Per-operation capability dispatch — the work the wall door does AFTER admit.

The wall (``spine.gateway.app.wall.Wall``) enforces access: route-exists ->
authn -> rate-limit -> schema -> RBAC -> ABAC -> consent -> approval ->
child-safety -> audit. It does NOT run the capability. Once ``admit`` returns a
:class:`WallResult`, *this* module dispatches to the real engine surface for the
loop capabilities and returns its (JSON-serialisable) result.

Design (ponytail — smallest diff that satisfies the spec):

  * A small registry maps a named operation (``evaluate_submission``,
    ``record_attempt``, ``record_practice``, ``generate_and_verify_content``,
    and the mastery / gap reads) to a thin handler that calls the EXISTING
    engine module function loaded under its alias by :mod:`backend.loader`.
  * Handlers REUSE the engine surfaces; they never re-implement the judgment.
  * ONE truth: mastery / gap come from the Python intelligence engine
    (``modules/learning/_engine.py`` -> ``spine/intelligence``). When that
    engine is unavailable (its pydantic dependency absent), the handler returns
    a clearly-labelled ``degraded`` result rather than crashing — the law is
    "degrade cleanly, never break the build".
  * An operation with NO registered handler falls back to the governed
    admission acknowledgment (``status: admitted``) the door always returned —
    so unmapped routes keep working and deny-by-default is untouched (dispatch
    only ever runs for a route the wall already ADMITTED).
  * Ladder ops carry the ``approval_token`` the wall validated; handlers echo
    it as ``approval_honored`` so the consequential rung is visible end-to-end.

Import-safe: importing this module performs no I/O and reads no secret value.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from . import loader

logger = logging.getLogger("clss.backend.dispatch")

# A handler takes the validated payload + the approval token (None unless a
# ladder op was approved) and returns a JSON-serialisable dict.
Handler = Callable[[dict[str, Any], Optional[str]], dict[str, Any]]


def _mod(name: str) -> Any:
    """Return a loaded capability module (under its alias), or None when absent.
    Cached by the loader; degrades cleanly to None so a handler can report a
    degraded result instead of raising."""
    return loader.load_capability_module(name)


def _degraded(operation: str, reason: str) -> dict[str, Any]:
    return {"dispatched": False, "operation": operation, "degraded": True, "reason": reason}


# --------------------------------------------------------------------------- #
# Handlers — each REUSES the existing engine surface. Thin by construction.
# --------------------------------------------------------------------------- #


def _evaluate_submission(payload: dict[str, Any], approval: Optional[str]) -> dict[str, Any]:
    """coursework.evaluate_submission — record a submission, run the three-mode
    engine, and emit the evidence the intelligence engine consumes.

    A consequential mark rides the PERMISSION LADDER: the engine never auto-
    finalises (the marking gate stays ``final=False``), and a consequential
    grade additionally REQUIRES a human approval token at the wall —
    ``awaiting_approval`` is surfaced when one was not presented. We emit the
    contract events through the EXISTING coursework event builders:
    ``submission.created`` (the submission is recorded), ``attempt.recorded``
    (per-response evidence carrying the independent-vs-supported flag the gap
    engine reads), and ``score.recorded`` (banded, human_final = the gate's
    truth). With no event store wired they validate-and-return (degraded),
    never fabricating a persisted mark.
    """
    mod = _mod("coursework")
    if mod is None:
        return _degraded("evaluate_submission", "coursework engine not loaded")
    try:
        from datetime import datetime, timezone
        from uuid import uuid4, UUID

        alias = loader._alias_for("mod", "coursework")
        ev = __import__(f"{alias}.evaluation", fromlist=["*"])
        events_mod = __import__(f"{alias}.events", fromlist=["*"])
        contracts = __import__(f"{alias}.contracts", fromlist=["*"])

        def _u(v: Any) -> Any:
            try:
                return UUID(str(v))
            except Exception:
                return uuid4()

        raw_responses = payload.get("responses") or []
        responses = []
        for r in raw_responses:
            responses.append(
                ev.ResponseInput(
                    question_ref=_u(r.get("question_ref")),
                    expression=r.get("expression"),
                    learner_answer=r.get("learner_answer"),
                    free_text=r.get("free_text"),
                    ocr_confidence=r.get("ocr_confidence"),
                    ocr_text_recovered=r.get("ocr_text_recovered", True),
                )
            )
        submission_ref = _u(payload.get("submission_ref"))
        subject = _u(payload.get("subject_uuid") or payload.get("scored_subject"))
        consequential = bool(payload.get("consequential", True))
        submission = ev.SubmissionInput(
            submission_ref=submission_ref,
            scored_subject=subject,
            responses=responses,
            consequential=consequential,
        )

        # Three modes, one engine. The mode selector keeps the named loop op a
        # single door; preventive is forced non-consequential by the engine.
        engine = ev.EvaluationEngine()
        mode = str(payload.get("mode", "post_submission")).lower()
        if mode in ("scanned", "scanned_handwriting", "handwriting"):
            outcome = engine.scanned_handwriting(submission)
        elif mode in ("preventive", "preventive_before_submission", "before"):
            outcome = engine.preventive_before_submission(submission)
        else:
            outcome = engine.post_submission(submission)
        gate = outcome.marking_gate

        # PERMISSION LADDER (grade): a consequential mark must not stand without a
        # human approval token. The wall admits the route; here we make the rung
        # legible — a consequential grade with no token is awaiting approval and
        # the engine result stays a recommendation, never a final mark.
        awaiting_approval = bool(gate.consequential and approval is None)

        # Emit the contract events the intelligence engine consumes. Reuse the
        # existing builders + the append-only sink (degraded with no store URL).
        emitter = events_mod.CourseworkEvents(sink=events_mod.InMemoryEventSink())
        purpose = str(payload.get("purpose", "assessment"))
        consent_ref = _u(payload.get("consent_ref"))
        ontology = payload.get("ontology") or {"topic_id": str(payload.get("topic_id") or uuid4())}
        now = datetime.now(timezone.utc)

        def _emit(type_: str, payload_: dict) -> dict:
            # ``emit`` is a coroutine that adapts to async sinks; with the sync
            # in-memory sink it never suspends, so we drive it to completion
            # without an event loop (the door route is already inside one, where
            # asyncio.run would raise). Reuses the module's emit; no new path.
            coro = emitter.emit(
                type=type_,
                canonical_uuid=subject,
                purpose=purpose,
                consent_ref=consent_ref,
                payload=payload_,
                occurred_at=now,
            )
            try:
                coro.send(None)
            except StopIteration as done:
                e = done.value
            else:  # pragma: no cover - a sync sink never suspends
                coro.close()
                raise RuntimeError("event sink unexpectedly suspended")
            return {"type": e.type, "persisted": e.persisted}

        emitted: list[dict] = []
        attempt_ids: list[UUID] = []
        # attempt.recorded — per response, the keystone independent flag.
        for resp_in, resp_ev in zip(raw_responses, outcome.responses):
            attempt_id = _u(resp_in.get("attempt_id"))
            attempt_ids.append(attempt_id)
            emitted.append(
                _emit(
                    "attempt.recorded",
                    emitter.build_attempt_evidence(
                        attempt_id=attempt_id,
                        ontology=resp_in.get("ontology") or ontology,
                        independent=bool(resp_in.get("independent", True)),
                        assistance_level=str(resp_in.get("assistance_level", "Independent")),
                        correct=resp_ev.answer_state is contracts.AnswerState.CORRECT,
                        difficulty=float(resp_in.get("difficulty", 0.5)),
                        time_taken_ms=int(resp_in.get("time_taken_ms", 0)),
                        question_id=resp_ev.question_ref,
                        score=resp_ev.normalized_score,
                    ),
                )
            )
        # submission.created — the submission is recorded.
        emitted.append(
            _emit(
                "submission.created",
                emitter.build_submission_created(
                    submission_id=submission_ref,
                    assignment_id=_u(payload.get("assignment_id")),
                    submitted_by=subject,
                    attempt_ids=attempt_ids,
                    submitted_at=now,
                ),
            )
        )
        # score.recorded — banded; human_final is the gate's truth (False here).
        emitted.append(
            _emit("score.recorded", emitter.build_score_recorded(outcome, ontology=ontology))
        )

        return {
            "dispatched": True,
            "operation": "evaluate_submission",
            "mode": contracts.score_mode_for(outcome.mode),
            "needs_human_review": outcome.needs_human_review,
            "recommended_score": outcome.recommended_score,
            "confidence_band": contracts.event_confidence_band_for(gate.engine_confidence_band),
            "consequential": gate.consequential,
            "final": gate.final,
            "awaiting_approval": awaiting_approval,
            "review_notes": list(outcome.review_notes),
            "events_emitted": emitted,
            "approval_honored": approval is not None,
        }
    except Exception as exc:  # degrade cleanly, never break the door
        logger.warning("evaluate_submission dispatch degraded: %s", exc)
        return _degraded("evaluate_submission", f"engine error: {type(exc).__name__}")


def _record_practice(payload: dict[str, Any], approval: Optional[str]) -> dict[str, Any]:
    """learning.record_practice / record_attempt — grade a topic quiz attempt.

    Reuses the deterministic, dependency-free ``grade_topic_quiz`` so it works
    offline (the intelligence engine is consulted for mastery via a separate
    read op). Comprehension-weighted, independence-leaning — the engine's truth.
    """
    mod = _mod("learning")
    if mod is None:
        return _degraded("record_practice", "learning engine not loaded")
    try:
        practice = __import__(f"{loader._alias_for('mod', 'learning')}.practice", fromlist=["*"])
        items = [
            practice.QuizItemResult(
                correct=bool(it.get("correct")),
                independent=bool(it.get("independent")),
                difficulty=float(it.get("difficulty", 0.5)),
                score=it.get("score"),
            )
            for it in (payload.get("items") or [])
        ]
        if not items:
            return _degraded("record_practice", "no practice items in payload")
        result = practice.grade_topic_quiz(payload.get("topic_id", "topic"), items)
        return {
            "dispatched": True,
            "operation": "record_practice",
            "topic_id": result.topic_id,
            "comprehension_score": result.comprehension_score,
            "independent_share": result.independent_share,
            "passed": result.passed,
            "plain_language": result.plain_language,
            "approval_honored": approval is not None,
        }
    except Exception as exc:
        logger.warning("record_practice dispatch degraded: %s", exc)
        return _degraded("record_practice", f"engine error: {type(exc).__name__}")


def _record_attempt(payload: dict[str, Any], approval: Optional[str]) -> dict[str, Any]:
    """learning.record_attempt — record ONE practice attempt as an evidence event.

    The LoopModules loop (b7/d13): a practice attempt records an event
    (correct/incorrect + the assistance level used) and EMITS it through the
    gateway-first emitter so it feeds the engine. Reuses the EXISTING
    ``practice.record_practice_attempt`` — the productive-struggle / no-answer-
    handover guard (unknown rung refused; the keystone flag derived from the rung,
    never assumed) lives there, not re-implemented here. The emitter degrades to
    the in-memory append-only sink when no gateway sink is wired; the result says
    so via ``delivered``.
    """
    mod = _mod("learning")
    if mod is None:
        return _degraded("record_attempt", "learning engine not loaded")
    try:
        practice = __import__(f"{loader._alias_for('mod', 'learning')}.practice", fromlist=["*"])
        record = practice.record_practice_attempt(
            canonical_uuid=str(payload.get("subject_uuid") or payload.get("canonical_uuid") or "subject"),
            consent_ref=str(payload.get("consent_ref") or "consent"),
            topic_id=str(payload.get("topic_id", "topic")),
            assistance_level=str(payload.get("assistance_level", "Hint")),
            correct=bool(payload.get("correct")),
            difficulty=float(payload.get("difficulty", 0.5)),
            time_taken_ms=int(payload.get("time_taken_ms", 0)),
            score=payload.get("score"),
            question_id=payload.get("question_id"),
            attempt_number=int(payload.get("attempt_number", 1)),
        )
        return {
            "dispatched": True,
            "operation": "record_attempt",
            "topic_id": record.topic_id,
            "assistance_level": record.assistance_level,
            "independent": record.independent,
            "correct": record.correct,
            "delivered": record.delivered,
            "sink": record.sink,
            "plain_language": record.plain_language,
            "event_id": record.event_id,
            "approval_honored": approval is not None,
        }
    except ValueError as exc:
        # The no-answer-handover guard refused an incoherent attempt — surface it.
        logger.warning("record_attempt refused: %s", exc)
        return _degraded("record_attempt", f"refused: {exc}")
    except Exception as exc:
        logger.warning("record_attempt dispatch degraded: %s", exc)
        return _degraded("record_attempt", f"engine error: {type(exc).__name__}")


def _generate_and_verify_content(payload: dict[str, Any], approval: Optional[str]) -> dict[str, Any]:
    """content.generate_and_verify_content — generate-and-verify + confidence gate.

    Serves material ONLY when the spine's confidence gate passes; otherwise
    returns the review reason (route to the human verification surface). Never
    fabricates: with no provider, the deterministic verifier path runs.
    """
    mod = _mod("content")
    if mod is None:
        return _degraded("generate_and_verify_content", "content engine not loaded")
    try:
        gen = __import__(f"{loader._alias_for('mod', 'content')}.generate", fromlist=["*"])
        kind_raw = str(payload.get("kind", "worked_example"))
        try:
            kind = gen.MaterialKind(kind_raw)
        except Exception:
            kind = next(iter(gen.MaterialKind))  # first declared kind as a safe default
        request = gen.MaterialRequest(
            topic_id=str(payload.get("topic_id", "topic")),
            kind=kind,
            payload=payload.get("content_payload") or {},
            difficulty=payload.get("difficulty"),
        )
        generator = gen.ContentGenerator()
        outcome = generator.generate(request)
        return {
            "dispatched": True,
            "operation": "generate_and_verify_content",
            "served": outcome.served,
            "provider_available": outcome.provider_available,
            "requires_approval": outcome.requires_approval,
            "review_reason": outcome.review_reason,
            "confidence": (outcome.material.confidence if outcome.material else None),
            "approval_honored": approval is not None,
        }
    except Exception as exc:
        logger.warning("generate_and_verify_content dispatch degraded: %s", exc)
        return _degraded("generate_and_verify_content", f"engine error: {type(exc).__name__}")


def _intel_engine() -> Any:
    """The ONE intelligence engine, loaded under its unique alias by
    :mod:`backend.intelligence_views` (NOT the bare ``import app`` bridge, which
    collides with other ``app`` packages loaded in this one process). Returns
    the engine module or None when unavailable."""
    from . import intelligence_views

    return intelligence_views._engine


def _to_uuid(v: Any) -> Any:
    from uuid import UUID

    return UUID(str(v))


def _mastery_read(payload: dict[str, Any], approval: Optional[str]) -> dict[str, Any]:
    """learning.mastery — read mastery from the CORE intelligence engine.

    ONE engine, one truth: mastery is authored by ``spine/intelligence`` and
    only READ here (via the topic projection). When the engine is unavailable
    (pydantic absent / not loaded), report a degraded read rather than
    re-deriving mastery — the surfaces fall back to the TS engine on degrade.
    """
    eng = _intel_engine()
    if eng is None:
        return _degraded("mastery", "intelligence engine not loaded")
    try:
        events = [eng.EventEnvelope.model_validate(e) for e in (payload.get("events") or [])]
        proj = eng.build_topic_projection(
            events,
            subject=_to_uuid(payload.get("subject") or payload.get("subject_uuid")),
            topic_id=_to_uuid(payload.get("topic_id")),
        )
        return {
            "dispatched": True,
            "operation": "mastery",
            "topic_id": payload.get("topic_id"),
            "dimensions": dict(getattr(proj.mastery.reading, "dimensions", {}) or {}),
            "plain_language": getattr(proj.mastery, "plain_language", None),
            "source": "engine",
        }
    except Exception as exc:
        logger.warning("mastery dispatch degraded: %s", exc)
        return _degraded("mastery", f"engine error: {type(exc).__name__}")


def _gap_read(payload: dict[str, Any], approval: Optional[str]) -> dict[str, Any]:
    """learning.gap — read detected gaps from the CORE intelligence engine."""
    eng = _intel_engine()
    if eng is None:
        return _degraded("gap", "intelligence engine not loaded")
    try:
        events = [eng.EventEnvelope.model_validate(e) for e in (payload.get("events") or [])]
        proj = eng.build_topic_projection(
            events,
            subject=_to_uuid(payload.get("subject") or payload.get("subject_uuid")),
            topic_id=_to_uuid(payload.get("topic_id")),
        )
        return {
            "dispatched": True,
            "operation": "gap",
            "topic_id": payload.get("topic_id"),
            "gaps": [str(getattr(g, "kind", g)) for g in (proj.gaps or [])],
            "source": "engine",
        }
    except Exception as exc:
        logger.warning("gap dispatch degraded: %s", exc)
        return _degraded("gap", f"engine error: {type(exc).__name__}")


# --------------------------------------------------------------------------- #
# The proactive loop: recommend -> approve -> execute (spine A5 workflow runtime).
# The wall ADMITTED the rung (EXECUTE is consequential -> the wall already forced
# the X-Approval-Token); here we drive the in-process workflow runtime and PERSIST
# the loop events (recommendation.created/actioned + approval.given +
# action.executed) to the event store via the seam. Reuses the workflow library's
# builders + the deployable's workflow binding; no judgment re-implemented here.
# ``actioned`` is the web's human-decision write (it maps to the APPROVE rung).
# --------------------------------------------------------------------------- #
def _loop_recommend(payload: dict[str, Any], approval: Optional[str]) -> dict[str, Any]:
    from . import workflow_app

    status, body = workflow_app.do_recommend(payload)
    return {"dispatched": status == 200, "operation": "recommend", **body}


def _loop_approve(payload: dict[str, Any], approval: Optional[str]) -> dict[str, Any]:
    from . import workflow_app

    status, body = workflow_app.do_approve(payload)
    return {
        "dispatched": status == 200,
        "operation": "approve",
        "approval_honored": approval is not None,
        **body,
    }


def _loop_execute(payload: dict[str, Any], approval: Optional[str]) -> dict[str, Any]:
    from . import workflow_app

    status, body = workflow_app.do_execute(payload)
    return {
        "dispatched": status == 200,
        "operation": "execute",
        "approval_honored": approval is not None,
        **body,
    }


# --------------------------------------------------------------------------- #
# Registry: (capability, operation) -> handler. Operation is the ORIGINAL,
# semantic name from the URL (before the door collapses it to a wall action),
# so the named loop ops dispatch to the right engine surface.
# --------------------------------------------------------------------------- #
# The loop is registered on the capabilities whose proactive behaviour the web
# drives: the intelligence-views feed (the web posts intelligence-views/actioned)
# and the generic workflow capability. ``actioned`` records the human decision.
_LOOP_CAPABILITIES = ("intelligence-views", "workflow", "learning")
_DISPATCH: dict[tuple[str, str], Handler] = {
    ("coursework", "evaluate_submission"): _evaluate_submission,
    ("learning", "record_practice"): _record_practice,  # grade a topic-quiz batch
    ("learning", "record_attempt"): _record_attempt,     # record + EMIT one attempt event (the loop)
    ("content", "generate_and_verify_content"): _generate_and_verify_content,
    ("learning", "mastery"): _mastery_read,
    ("learning", "gap"): _gap_read,
}
for _cap in _LOOP_CAPABILITIES:
    _DISPATCH[(_cap, "recommend")] = _loop_recommend
    _DISPATCH[(_cap, "approve")] = _loop_approve
    _DISPATCH[(_cap, "actioned")] = _loop_approve  # the web's human-decision write
    _DISPATCH[(_cap, "execute")] = _loop_execute


def has_handler(capability: str, operation: str) -> bool:
    return (capability, operation.lower()) in _DISPATCH


def dispatch(
    capability: str, operation: str, payload: dict[str, Any], approval_token: Optional[str]
) -> Optional[dict[str, Any]]:
    """Invoke the engine operation for an ADMITTED route. Returns the handler's
    JSON-serialisable result, or None when no handler is registered (the door
    then returns its governed admission acknowledgment). Only ever called AFTER
    the wall admits, so deny-by-default is untouched."""
    handler = _DISPATCH.get((capability, operation.lower()))
    if handler is None:
        return None
    return handler(payload or {}, approval_token)
