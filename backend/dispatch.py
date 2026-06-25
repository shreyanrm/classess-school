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


def _alias(name: str) -> str:
    return loader._alias_for("mod", name)


def _emit_capability_event(
    *, app_: str, type_: str, payload: dict[str, Any], subject: Any, consent_ref: Any
) -> dict[str, Any]:
    """Append a clean, attributed, consent-stamped event for a consequential
    capability action through the EVENT-STORE seam — so the circuit is
    identity -> gateway -> capability -> EVENT (persisted, never an echo). Reuses
    the deployable's append-only sink; degrades to ``persisted: False`` with no
    store wired. PII-free: opaque subject ref + consent ref only."""
    from datetime import datetime, timezone
    from uuid import uuid4

    from . import event_sink

    return event_sink.append_emit_input(
        {
            "app": app_,
            "canonical_uuid": str(subject or uuid4()),
            "purpose": "intervention",
            "consent_ref": str(consent_ref or uuid4()),
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "type": type_,
            "payload": payload,
        }
    )


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
# GAP#10 — the Wave-2 feature-module fronts, routed through the gateway and
# dispatched in-process behind the wall. Each handler is THIN: it REUSES the
# module's EXISTING logic (it never re-implements the judgment) and, for a
# consequential write, appends a clean attributed event so the circuit is
# identity -> gateway -> capability -> event. A degraded module returns a clearly
# labelled degraded result rather than crashing the door.
# --------------------------------------------------------------------------- #


# --- communication (b9) ---------------------------------------------------- #
def _comm_translate(payload: dict[str, Any], approval: Optional[str]) -> dict[str, Any]:
    """communication.translate (GAP#8) — render text into the READER's preferred
    language, preserving subject terminology + code-switch spans. Reuses the
    EXISTING ``translation.render_for_reader``; degrades to a content-preserving
    passthrough (never drops or fabricates text). A READ — no event/approval."""
    mod = _mod("communication")
    if mod is None:
        return _degraded("translate", "communication module not loaded")
    try:
        translation = __import__(f"{_alias('communication')}.translation", fromlist=["*"])
        iface = translation.TranslationInterface()
        result = iface.render_for_reader(
            str(payload.get("text", "")),
            preferred_lang=payload.get("preferred_lang") or payload.get("target_lang"),
            source_lang=str(payload.get("source_lang", "und")),
        )
        return {
            "dispatched": True,
            "operation": "translate",
            "rendered_text": result.rendered_text,
            "source_lang": result.source_lang,
            "target_lang": result.target_lang,
            "status": result.status,
            "preserved_terms": list(result.preserved_terms),
            "provider": result.provider,
        }
    except Exception as exc:
        logger.warning("translate dispatch degraded: %s", exc)
        return _degraded("translate", f"engine error: {type(exc).__name__}")


def _comm_make_tasks(payload: dict[str, Any], approval: Optional[str]) -> dict[str, Any]:
    """communication.make_tasks (GAP#9) — conversation-to-task: screen a free-text
    message then promote it into an owned, tracked task. Reuses the EXISTING
    ``hub.post`` (always screened — no unmonitored channel) + ``hub.route_to_task``
    (cross-context routing is consent-gated, fail-closed). Promoting a task is
    consequential -> emit ``communication.task_created``."""
    mod = _mod("communication")
    if mod is None:
        return _degraded("make_tasks", "communication module not loaded")
    try:
        hub = __import__(f"{_alias('communication')}.hub", fromlist=["*"])
        h = hub.CommunicationHub()
        message = h.post(
            surface=str(payload.get("surface", "hub")),
            sender_ref=str(payload.get("sender_ref") or payload.get("subject_uuid") or "sender"),
            context_ref=str(payload.get("context_ref", "ctx")),
            body=str(payload.get("body", "")),
        )
        task = h.route_to_task(
            message,
            title=str(payload.get("title", "Follow up")),
            owner_role=str(payload.get("owner_role", "teacher")),
            owner_ref=str(payload.get("owner_ref") or payload.get("subject_uuid") or "owner"),
            why=str(payload.get("why", "Routed from a conversation.")),
            due_date=payload.get("due_date"),
            target_context_ref=payload.get("target_context_ref"),
            consent_ref=payload.get("consent_ref"),
        )
        event = _emit_capability_event(
            app_="communication",
            type_="communication.task_created",
            payload={"task_id": task.task_id, "owner_role": task.owner_role,
                     "from_message_id": task.from_message_id, "flagged": message.is_flagged},
            subject=payload.get("subject_uuid") or payload.get("owner_ref"),
            consent_ref=payload.get("consent_ref"),
        )
        return {
            "dispatched": True,
            "operation": "make_tasks",
            "task_id": task.task_id,
            "owner_role": task.owner_role,
            "needs_human": message.needs_human,
            "event": event,
            "approval_honored": approval is not None,
        }
    except PermissionError as exc:  # ConsentError — cross-context routing refused
        logger.warning("make_tasks consent-refused: %s", exc)
        return _degraded("make_tasks", f"consent_required: {exc}")
    except Exception as exc:
        logger.warning("make_tasks dispatch degraded: %s", exc)
        return _degraded("make_tasks", f"engine error: {type(exc).__name__}")


def _ptm_available_slot(payload: dict[str, Any], ptm: Any) -> Any:
    """Source a real PTM slot from a SCHEDULING/AVAILABILITY read — not a hard-
    coded literal. The owner's free window is derived from the scheduling
    module's academic calendar (the next working day on/after the requested
    anchor); the within-day window comes from the requested time band. An
    explicit ``slot_id``/``starts_at`` in the payload still overrides (a surface
    that already picked a concrete offered slot). When scheduling is unavailable,
    degrade to a COMPUTED slot (the next calendar weekday from today) rather than
    a fixed date — still derived, never a frozen literal."""
    from datetime import date, datetime, time, timedelta, timezone

    owner_ref = str(payload.get("teacher_ref") or payload.get("subject_uuid") or "teacher")
    owner_role = str(payload.get("owner_role", "teacher"))
    # An explicit, surface-chosen slot wins (the human already picked it).
    if payload.get("starts_at"):
        starts_at = str(payload["starts_at"])
        return ptm.MeetingSlot(
            slot_id=str(payload.get("slot_id", f"slot-{starts_at}")),
            owner_ref=owner_ref, owner_role=owner_role, starts_at=starts_at,
            window_label=str(payload.get("window_label", starts_at)),
        )

    anchor = date.fromisoformat(payload["after"]) if payload.get("after") else date.today()
    # The within-day window (e.g. a 15:30 PTM band). Read, not hard-coded literal.
    band_hour = int(payload.get("window_hour", 15))
    band_min = int(payload.get("window_minute", 30))
    duration_min = int(payload.get("duration_minutes", 15))

    meeting_day: date | None = None
    mod = _mod("scheduling")
    if mod is not None:
        try:
            cal = __import__(f"{_alias('scheduling')}.calendar", fromlist=["*"])
            # Build the availability calendar from the payload's term window when
            # supplied; the calendar's working-pattern + holiday math is the
            # authority for which day is actually free (not a literal).
            terms = []
            for t in payload.get("terms") or []:
                terms.append(cal.Term(term_id=str(t.get("term_id", "term")),
                                      label=str(t.get("label", "Term")),
                                      start=date.fromisoformat(t["start"]),
                                      end=date.fromisoformat(t["end"])))
            if not terms:
                # Default availability horizon: a term running from the anchor.
                terms = [cal.Term(term_id="term", label="Term", start=anchor,
                                  end=anchor + timedelta(days=120))]
            academic = cal.AcademicCalendar(
                institution_id=str(payload.get("institution_id", "inst")),
                label="availability", terms=terms,
            )
            meeting_day = academic.next_working_day(anchor, inclusive=False)
        except Exception as exc:  # degrade to a computed weekday, never a literal
            logger.warning("scheduling availability read degraded: %s", exc)
            meeting_day = None
    if meeting_day is None:
        # Computed fallback: next weekday (Mon-Fri) after the anchor. Derived.
        meeting_day = anchor + timedelta(days=1)
        while meeting_day.weekday() >= 5:
            meeting_day += timedelta(days=1)

    starts = datetime.combine(meeting_day, time(hour=band_hour, minute=band_min, tzinfo=timezone.utc))
    end = starts + timedelta(minutes=duration_min)
    window_label = (f"{meeting_day.strftime('%a')} "
                    f"{starts.strftime('%H:%M')}-{end.strftime('%H:%M')}")
    return ptm.MeetingSlot(
        slot_id=f"slot-{meeting_day.isoformat()}-{band_hour:02d}{band_min:02d}",
        owner_ref=owner_ref, owner_role=owner_role,
        starts_at=starts.isoformat(), window_label=window_label,
    )


def _comm_ptm(payload: dict[str, Any], approval: Optional[str]) -> dict[str, Any]:
    """communication.ptm (GAP#12) — prepare a parent-teacher meeting booking
    (PROPOSED, awaiting human confirm — the RECOMMEND rung) and the parent's
    screened prep. Reuses the EXISTING ``ptm.PtmService``; the offered slot is
    sourced from a SCHEDULING/AVAILABILITY read (``_ptm_available_slot``), not a
    hard-coded literal. The booking request is consequential prep -> emit
    ``ptm.requested``."""
    mod = _mod("communication")
    if mod is None:
        return _degraded("ptm", "communication module not loaded")
    try:
        ptm = __import__(f"{_alias('communication')}.ptm", fromlist=["*"])
        svc = ptm.PtmService()
        slot = _ptm_available_slot(payload, ptm)
        booking = svc.request_booking(
            slot=slot,
            parent_ref=str(payload.get("parent_ref", "parent")),
            child_context_ref=str(payload.get("child_context_ref", "child")),
        )
        prep = svc.prepare(
            booking=booking,
            child_brief=str(payload.get("child_brief", "A short shared conversation about support.")),
            question_bodies=payload.get("question_bodies") or [],
        )
        event = _emit_capability_event(
            app_="communication",
            type_="ptm.requested",
            payload={"booking_id": booking.booking_id, "status": booking.status.value
                     if hasattr(booking.status, "value") else str(booking.status)},
            subject=payload.get("subject_uuid") or payload.get("parent_ref"),
            consent_ref=payload.get("consent_ref"),
        )
        return {
            "dispatched": True,
            "operation": "ptm",
            "booking_id": booking.booking_id,
            "is_confirmed": booking.is_confirmed,
            "question_count": prep.question_count,
            "event": event,
            "approval_honored": approval is not None,
        }
    except RuntimeError as exc:  # PtmQuestionFlaggedError — safeguarding
        logger.warning("ptm question flagged: %s", exc)
        return _degraded("ptm", f"safeguarding: {exc}")
    except Exception as exc:
        logger.warning("ptm dispatch degraded: %s", exc)
        return _degraded("ptm", f"engine error: {type(exc).__name__}")


def _comm_parent_feedback(payload: dict[str, Any], approval: Optional[str]) -> dict[str, Any]:
    """communication.parent_feedback — generate-and-verify parent feedback FROM
    real signals (grounded + confidence-gated; never canned). Reuses the EXISTING
    ``parent_feedback.ParentFeedbackGenerator``. A READ-shaped generation."""
    mod = _mod("communication")
    if mod is None:
        return _degraded("parent_feedback", "communication module not loaded")
    try:
        pf = __import__(f"{_alias('communication')}.parent_feedback", fromlist=["*"])
        signals = []
        for s in payload.get("signals") or []:
            try:
                kind = pf.SignalKind(str(s.get("kind")))
            except Exception:
                continue
            signals.append(
                pf.ProgressSignal(
                    kind=kind,
                    subject=str(s.get("subject", "")),
                    descriptor=str(s.get("descriptor") or s.get("summary", "")),
                    confidence=float(s.get("confidence", 0.0)),
                )
            )
        feedback = pf.ParentFeedbackGenerator().generate(
            child_uuid=str(payload.get("child_uuid") or payload.get("subject_uuid") or "child"),
            signals=signals,
        )
        return {
            "dispatched": True,
            "operation": "parent_feedback",
            "parts": [p.kind for p in feedback.parts],
            "withheld_notes": list(feedback.withheld_notes),
        }
    except Exception as exc:
        logger.warning("parent_feedback dispatch degraded: %s", exc)
        return _degraded("parent_feedback", f"engine error: {type(exc).__name__}")


# --- institution (b1) ------------------------------------------------------ #
def _institution_policy(payload: dict[str, Any], approval: Optional[str]) -> dict[str, Any]:
    """institution.policy / config — read the module's settings (policy/config
    surface). Reuses the EXISTING ``config.get_settings`` (env-var NAMES only,
    never a secret value). A READ."""
    mod = _mod("institution")
    if mod is None:
        return _degraded("policy", "institution module not loaded")
    try:
        config = __import__(f"{_alias('institution')}.config", fromlist=["*"])
        settings = config.get_settings()
        return {
            "dispatched": True,
            "operation": "policy",
            "service_name": settings.service_name,
            "env": settings.env,
            # NAMES/booleans only — never a secret value.
            "gateway_configured": settings.gateway_url is not None,
            "event_sink_configured": settings.event_sink_url is not None,
        }
    except Exception as exc:
        logger.warning("institution.policy dispatch degraded: %s", exc)
        return _degraded("policy", f"engine error: {type(exc).__name__}")


# --- scheduling (b2) ------------------------------------------------------- #
def _scheduling_recommend_recovery(payload: dict[str, Any], approval: Optional[str]) -> dict[str, Any]:
    """scheduling.recommend_recovery — recommend recovery actions for a drifting
    pacing finding (RECOMMEND rung; never applies anything). Reuses the EXISTING
    ``recovery.recommend_recovery`` over a ``PacingStatus`` built from payload."""
    mod = _mod("scheduling")
    if mod is None:
        return _degraded("recommend_recovery", "scheduling module not loaded")
    try:
        from datetime import date

        recovery = __import__(f"{_alias('scheduling')}.recovery", fromlist=["*"])
        pacing = __import__(f"{_alias('scheduling')}.pacing", fromlist=["*"])
        status = pacing.PacingStatus(
            section_id=str(payload.get("section_id", "sec-1")),
            subject_id=str(payload.get("subject_id", "sub-1")),
            as_of=date.fromisoformat(payload["as_of"]) if payload.get("as_of") else date.today(),
            working_days_elapsed=int(payload.get("working_days_elapsed", 40)),
            expected_periods=float(payload.get("expected_periods", 40.0)),
            delivered_periods=int(payload.get("delivered_periods", 30)),
            owner_ref=str(payload.get("owner_ref") or payload.get("subject_uuid") or ""),
        )
        actions = recovery.recommend_recovery(status, owner_ref=status.owner_ref)
        return {
            "dispatched": True,
            "operation": "recommend_recovery",
            "is_drifting": status.is_drifting,
            "actions": [
                {"action_id": a.action_id, "kind": a.kind.value if hasattr(a.kind, "value") else str(a.kind)}
                for a in actions
            ],
        }
    except Exception as exc:
        logger.warning("recommend_recovery dispatch degraded: %s", exc)
        return _degraded("recommend_recovery", f"engine error: {type(exc).__name__}")


# --- attendance (b5) ------------------------------------------------------- #
def _attendance_capture(payload: dict[str, Any], approval: Optional[str]) -> dict[str, Any]:
    """attendance.capture — assist a roll via absent-only marking (a PROPOSAL,
    never final until a human confirms — the permission ladder). Reuses the
    EXISTING ``capture.capture_absent_only`` + ``summarize_draft``."""
    mod = _mod("attendance")
    if mod is None:
        return _degraded("capture", "attendance module not loaded")
    try:
        capture = __import__(f"{_alias('attendance')}.capture", fromlist=["*"])
        roll = capture.capture_absent_only(
            session_id=str(payload.get("session_id", "session-1")),
            roster_refs=[str(r) for r in (payload.get("roster_refs") or [])],
            absent_refs=[str(r) for r in (payload.get("absent_refs") or [])],
        )
        summary = capture.summarize_draft(roll)
        return {
            "dispatched": True,
            "operation": "capture",
            "session_id": roll.session_id,
            "is_final": roll.is_final,  # a proposal — final only after human confirm
            "summary": summary,
        }
    except Exception as exc:
        logger.warning("attendance.capture dispatch degraded: %s", exc)
        return _degraded("capture", f"engine error: {type(exc).__name__}")


# --- teacher-growth (b10) -------------------------------------------------- #
def _teacher_growth_coaching(payload: dict[str, Any], approval: Optional[str]) -> dict[str, Any]:
    """teacher-growth.coaching — build the explainable, NON-punitive coaching
    summary from one lesson's interaction metrics. Reuses the EXISTING
    ``build_coaching_summary`` (the no-ranking / no-employment-decision guard
    lives there). A READ; never an employment judgment."""
    mod = _mod("teacher-growth")
    if mod is None:
        return _degraded("coaching", "teacher-growth module not loaded")
    try:
        interaction = __import__(f"{_alias('teacher-growth')}.interaction", fromlist=["*"])
        coaching = __import__(f"{_alias('teacher-growth')}.coaching", fromlist=["*"])
        metrics = interaction.InteractionMetrics(
            lesson_id=str(payload.get("lesson_id", "lesson-1")),
            teacher_ref=str(payload.get("teacher_ref") or payload.get("subject_uuid") or "teacher"),
            teacher_talk_s=float(payload.get("teacher_talk_s", 600.0)),
            learner_talk_s=float(payload.get("learner_talk_s", 400.0)),
            total_questions=int(payload.get("total_questions", 10)),
            higher_order_questions=int(payload.get("higher_order_questions", 4)),
            lower_order_questions=int(payload.get("lower_order_questions", 6)),
            wait_time_samples=[float(x) for x in (payload.get("wait_time_samples") or [])],
        )
        summary = coaching.build_coaching_summary(metrics)
        return {
            "dispatched": True,
            "operation": "coaching",
            "lesson_id": metrics.lesson_id,
            # Teacher-first, NON-punitive: dimensions + plain readings, never a rating.
            "strengths": [str(s.dimension.value if hasattr(s.dimension, "value") else s.dimension)
                          for s in summary.strengths],
            "growth_areas": [str(s.dimension.value if hasattr(s.dimension, "value") else s.dimension)
                             for s in summary.growth_areas],
            "framing": summary.framing(),
        }
    except Exception as exc:
        logger.warning("teacher-growth.coaching dispatch degraded: %s", exc)
        return _degraded("coaching", f"engine error: {type(exc).__name__}")


# --- governance (b/A7: GAP#3/#5/#7) ---------------------------------------- #
# AI-control toggle / break-glass / policy-version PERSIST + emit an immutable
# audit event; the audit-trail is a READ. Reuses backend.governance_app (which
# reuses the spine/governance control plane). Toggle/breakglass/policy-version
# route onto the EXECUTE rung (consequential -> the wall forced the approval
# token); the audit trail is a plain read.
def _gov_toggle(payload: dict[str, Any], approval: Optional[str]) -> dict[str, Any]:
    from . import governance_app

    status, body = governance_app.do_toggle(payload)
    return {"dispatched": status == 200, "operation": "toggle",
            "approval_honored": approval is not None, **body}


def _gov_breakglass(payload: dict[str, Any], approval: Optional[str]) -> dict[str, Any]:
    from . import governance_app

    status, body = governance_app.do_breakglass(payload)
    return {"dispatched": status == 200, "operation": "breakglass",
            "approval_honored": approval is not None, **body}


def _gov_policy_version(payload: dict[str, Any], approval: Optional[str]) -> dict[str, Any]:
    from . import governance_app

    status, body = governance_app.do_policy_version(payload)
    return {"dispatched": status == 200, "operation": "policy_version",
            "approval_honored": approval is not None, **body}


def _gov_audit_trail(payload: dict[str, Any], approval: Optional[str]) -> dict[str, Any]:
    from . import governance_app

    status, body = governance_app.do_audit_trail(payload)
    return {"dispatched": status == 200, "operation": "audit_trail", **body}


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


# --------------------------------------------------------------------------- #
# CONCRETE EXECUTORS — the credentialled capability that PERFORMS a cleared,
# post-approval action (INVARIANT 8: the workflow package AUTHORISES; THIS layer,
# acting as the credentialled capability behind the gateway, PERFORMS). The
# workflow ``execute`` gate returns ``cleared=True, performed=False`` for a
# consequential action ("a governed capability is now authorised"); only AFTER
# that clearance do these executors fire the REVERSIBLE side effect and report
# ``performed=True``. Each reuses the module's EXISTING surface; none re-derives
# judgment, and none fires without clearance. Consequential/irreversible ops are
# NOT wired here — they stay authorised-but-not-auto-performed.
# --------------------------------------------------------------------------- #
def _exec_make_tasks(payload: dict[str, Any]) -> dict[str, Any]:
    """Reversible: promote a screened message into an owned, tracked task (a task
    can be closed/reassigned). Reuses communication ``hub.post`` + ``route_to_task``."""
    return _comm_make_tasks(payload, "cleared")


def _exec_attendance_mark(payload: dict[str, Any]) -> dict[str, Any]:
    """Reversible: finalise (confirm) an attendance roll with the approving human's
    opaque ref. Reuses attendance ``capture.capture_absent_only`` + ``confirm_roll``
    (the single human-attributed path to a finalised roll). A finalised roll can
    later be corrected by an authorising human, so the act is reversible."""
    mod = _mod("attendance")
    if mod is None:
        return _degraded("attendance_mark", "attendance module not loaded")
    capture = __import__(f"{_alias('attendance')}.capture", fromlist=["*"])
    confirmed_by = str(payload.get("confirmed_by") or payload.get("decided_by")
                       or payload.get("subject_uuid") or "")
    if not confirmed_by.strip():
        return _degraded("attendance_mark", "confirm requires an opaque human ref (confirmed_by)")
    roll = capture.capture_absent_only(
        session_id=str(payload.get("session_id", "session-1")),
        roster_refs=[str(r) for r in (payload.get("roster_refs") or [])],
        absent_refs=[str(r) for r in (payload.get("absent_refs") or [])],
    )
    final = capture.confirm_roll(roll, confirmed_by=confirmed_by, note=payload.get("note"))
    event = _emit_capability_event(
        app_="attendance",
        type_="attendance.finalised",
        payload={"session_id": final.session_id, "is_final": final.is_final,
                 "confirmed_by": "[opaque]"},
        subject=payload.get("subject_uuid") or payload.get("session_id"),
        consent_ref=payload.get("consent_ref"),
    )
    return {"performed": True, "operation": "attendance_mark",
            "session_id": final.session_id, "is_final": final.is_final, "event": event}


def _exec_message_send(payload: dict[str, Any]) -> dict[str, Any]:
    """Reversible: post a screened message to the monitored hub (a posted message
    can be retracted/superseded). Reuses communication ``hub.post`` — ALWAYS
    screened, so a flagged message rides its escalation rather than being dropped."""
    mod = _mod("communication")
    if mod is None:
        return _degraded("message_send", "communication module not loaded")
    hub = __import__(f"{_alias('communication')}.hub", fromlist=["*"])
    message = hub.CommunicationHub().post(
        surface=str(payload.get("surface", "hub")),
        sender_ref=str(payload.get("sender_ref") or payload.get("subject_uuid") or "sender"),
        context_ref=str(payload.get("context_ref", "ctx")),
        body=str(payload.get("body", "")),
    )
    event = _emit_capability_event(
        app_="communication",
        type_="communication.message_sent",
        payload={"message_id": message.message_id, "flagged": message.is_flagged,
                 "needs_human": message.needs_human},
        subject=payload.get("subject_uuid") or payload.get("sender_ref"),
        consent_ref=payload.get("consent_ref"),
    )
    return {"performed": True, "operation": "message_send",
            "message_id": message.message_id, "needs_human": message.needs_human, "event": event}


# Map the cleared action's effect to its concrete reversible executor. The key is
# the action's ``effect`` label the surface attaches to the execute payload (or
# the recommendation's action kind). Only REVERSIBLE safe actions are listed.
_EXECUTORS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "make_tasks": _exec_make_tasks,
    "create_task": _exec_make_tasks,
    "attendance_mark": _exec_attendance_mark,
    "mark_attendance": _exec_attendance_mark,
    "message_send": _exec_message_send,
    "send_message": _exec_message_send,
    "send": _exec_message_send,
}


def _perform_cleared_action(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Perform the concrete reversible side effect for a CLEARED execute, or None
    when the named effect has no wired executor (then it stays authorised-but-not-
    auto-performed — the workflow result already carries the action.executed
    clearance event). Degrades cleanly: an executor error is reported, never
    crashes the door."""
    effect = str(payload.get("effect") or payload.get("action_kind")
                 or payload.get("effect_verb") or "").strip().lower()
    executor = _EXECUTORS.get(effect)
    if executor is None:
        return None
    try:
        return executor(payload)
    except PermissionError as exc:  # consent refusal surfaces, never crashes
        logger.warning("cleared executor %s consent-refused: %s", effect, exc)
        return {"performed": False, "operation": effect, "degraded": True,
                "reason": f"consent_required: {exc}"}
    except Exception as exc:
        logger.warning("cleared executor %s degraded: %s", effect, exc)
        return {"performed": False, "operation": effect, "degraded": True,
                "reason": f"executor error: {type(exc).__name__}"}


def _loop_execute(payload: dict[str, Any], approval: Optional[str]) -> dict[str, Any]:
    from . import workflow_app

    status, body = workflow_app.do_execute(payload)
    out = {
        "dispatched": status == 200,
        "operation": "execute",
        "approval_honored": approval is not None,
        **body,
    }
    # INVARIANT 8: perform the concrete reversible side effect ONLY after the
    # workflow gate cleared the action (human approval recorded). The workflow
    # package authorised it; here, as the credentialled capability, we PERFORM.
    if body.get("cleared") and not body.get("performed"):
        performed = _perform_cleared_action(payload)
        if performed is not None:
            out["execution"] = performed
            out["performed"] = bool(performed.get("performed"))
    return out


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
    # GAP#10 — the Wave-2 feature-module fronts, routed through the gateway.
    # communication (b9): translation / conversation-to-task / ptm / feedback.
    ("communication", "translate"): _comm_translate,            # GAP#8
    ("communication", "make_tasks"): _comm_make_tasks,          # GAP#9
    ("communication", "ptm"): _comm_ptm,                        # GAP#12
    ("communication", "parent_feedback"): _comm_parent_feedback,
    # institution (b1): the policy/config read surface.
    ("institution", "policy"): _institution_policy,
    # scheduling (b2): pacing-recovery recommendations (the RECOMMEND rung).
    ("scheduling", "recommend_recovery"): _scheduling_recommend_recovery,
    # attendance (b5): assist a roll (a proposal; final only on human confirm).
    ("attendance", "capture"): _attendance_capture,
    # teacher-growth (b10): the non-punitive coaching summary.
    ("teacher-growth", "coaching"): _teacher_growth_coaching,
    # governance (GAP#3/#5/#7): toggle / break-glass / policy-version PERSIST +
    # emit an immutable audit event; audit-trail is the READ.
    ("governance", "toggle"): _gov_toggle,
    ("governance", "breakglass"): _gov_breakglass,
    ("governance", "policy_version"): _gov_policy_version,
    ("governance", "audit_trail"): _gov_audit_trail,
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
