"""Turn the immutable event stream into LEARNING SIGNALS (spine A4 — Track 2).

The event store is the signal source: every meaningful action emits a clean,
attributed, PII-free event (INVARIANT 5). This module replays those events and
distils them into ``LearningSignal`` records — the (input, output, reward,
task_class) tuples a small edge student can learn from.

Hard rules enforced here:

* INVARIANT 1/2 — a signal carries ONLY the opaque ``canonical_uuid``. It NEVER
  carries PII. The capture builders only ever read contract fields that are
  PII-free by construction; :func:`assert_pii_free` is a belt-and-braces scan
  that refuses to emit a signal containing anything that looks like PII.
* INVARIANT 6 — every signal carries its ``consent_ref`` + ``age_tier`` and is
  marked admissible ONLY if the consent gate permits model-improvement use. An
  inadmissible signal is still produced (for transparent provenance/audit) but
  is flagged ``admissible=False`` and never reaches a dataset.

A ``LearningSignal`` is deliberately small and serialisable: it is the unit the
dataset builder deduplicates, scrubs, and versions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from .consent_gate import AgeTier, ConsentGate

# Task classes the edge student is trained on. These map to the high-frequency
# "ocean" Track 2 serves and to platform-meaningful eval metrics.
TASK_HINT_GENERATION = "content.generate-hint"
TASK_INTENT_CLASSIFY = "classify.intent"
TASK_MASTERY_PREDICT = "predict.mastery-band"
TASK_GAP_CLASSIFY = "classify.gap-type"
TASK_REFUSAL = "safety.refuse"

# PII patterns — capture refuses any signal whose text fields match these. The
# contract should never put PII here; this is defence in depth, not the primary
# control (the primary control is that signals are built only from PII-free
# contract fields).
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# A bare phone number: 10+ digits optionally grouped by spaces. We strip opaque
# UUIDs FIRST (they are not PII) so their digit runs do not false-positive.
_PHONE = re.compile(r"(?<![\w])(?:\+?\d[\s\-]?){10,}(?![\w])")
# Opaque UUIDs are identifiers, never PII — removed before the phone scan.
_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
# A run of capitalised words that looks like a person's full name.
_PERSON_NAME = re.compile(r"\b([A-Z][a-z]{1,})\s+([A-Z][a-z]{1,})(?:\s+[A-Z][a-z]{1,})?\b")


class PiiLeakError(ValueError):
    """Raised when a value destined for a signal/dataset contains apparent PII."""


def assert_pii_free(value: Any, *, where: str = "signal") -> None:
    """Refuse strings (recursively) that look like PII. INVARIANT 1/2.

    UUIDs / opaque ids are fine (they are not PII). This scans free text only.
    """
    if isinstance(value, str):
        if _EMAIL.search(value):
            raise PiiLeakError(f"apparent email in {where}")
        # Strip opaque UUIDs (identifiers, not PII) before scanning for a phone
        # number so their digit runs cannot false-positive.
        without_uuids = _UUID_RE.sub(" ", value)
        if _PHONE.search(without_uuids):
            raise PiiLeakError(f"apparent phone number in {where}")
        if _PERSON_NAME.search(value):
            raise PiiLeakError(f"apparent personal name in {where}")
    elif isinstance(value, dict):
        for k, v in value.items():
            assert_pii_free(k, where=where)
            assert_pii_free(v, where=where)
    elif isinstance(value, (list, tuple)):
        for v in value:
            assert_pii_free(v, where=where)


@dataclass(frozen=True)
class LearningSignal:
    """A single PII-free training signal distilled from one or more events.

    * ``input`` / ``output`` are the model's prompt and target (text or a small
      structured label), carrying NO PII.
    * ``reward`` is the feedback/quality signal in [0,1] (correctness, score,
      verify-confidence) used to weight or filter the example.
    * ``task_class`` selects the head/objective the example trains.
    * ``consent_ref`` + ``age_tier`` + ``admissible`` carry the consent
      provenance: only an admissible signal may enter a dataset.
    """

    signal_id: str
    canonical_uuid: UUID
    task_class: str
    input: str
    output: str
    reward: float
    consent_ref: UUID
    age_tier: AgeTier | None
    admissible: bool
    source_event_ids: tuple[UUID, ...] = ()
    occurred_at: datetime | None = None
    # Verify provenance (set by curate for outputs that must pass generate-and-
    # verify before becoming a positive target). PII-free.
    verify_passed: bool | None = None
    verify_confidence: float | None = None
    meta: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Belt-and-braces: no signal is ever constructed with PII in its text.
        assert_pii_free(self.input, where="signal.input")
        assert_pii_free(self.output, where="signal.output")
        assert_pii_free(self.meta, where="signal.meta")


def _uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _signal_id(event_id: object, task_class: str) -> str:
    # Deterministic, opaque id derived from the event + task (no PII, no time).
    return f"{task_class}:{event_id}"


class SignalCapture:
    """Replays events into learning signals, stamping consent admissibility.

    The capture is PURE over its inputs: same events + same consent gate produce
    the same signals (modulo nothing). It does NOT read the network and never
    touches the PII vault.
    """

    def __init__(self, consent_gate: ConsentGate) -> None:
        self._gate = consent_gate

    def capture_event(self, event: dict) -> list[LearningSignal]:
        """Distil zero or more signals from a single event envelope."""
        etype = event.get("type")
        builder = _BUILDERS.get(etype)
        if builder is None:
            return []
        raw = builder(event)
        out: list[LearningSignal] = []
        for spec in raw:
            out.append(self._stamp(event, spec))
        return out

    def capture_stream(self, events: list[dict]) -> list[LearningSignal]:
        """Distil signals from a stream of events, in order."""
        signals: list[LearningSignal] = []
        for ev in events:
            signals.extend(self.capture_event(ev))
        return signals

    def admissible_signals(self, events: list[dict]) -> list[LearningSignal]:
        """Capture, then keep ONLY the consent-admissible signals (INVARIANT 6)."""
        return [s for s in self.capture_stream(events) if s.admissible]

    def _stamp(self, event: dict, spec: "_SignalSpec") -> LearningSignal:
        canonical_uuid = _uuid(event["canonical_uuid"])
        consent_ref = _uuid(event["consent_ref"])
        decision = self._gate.evaluate(canonical_uuid=canonical_uuid, consent_ref=consent_ref)
        return LearningSignal(
            signal_id=_signal_id(event.get("event_id", spec.fallback_id), spec.task_class),
            canonical_uuid=canonical_uuid,
            task_class=spec.task_class,
            input=spec.input,
            output=spec.output,
            reward=spec.reward,
            consent_ref=consent_ref,
            age_tier=decision.age_tier,
            admissible=decision.admissible,
            source_event_ids=tuple(_uuid(e) for e in spec.source_event_ids) or (
                (_uuid(event["event_id"]),) if event.get("event_id") else ()
            ),
            occurred_at=event.get("occurred_at"),
            meta={"deny_reason": decision.deny_reason.value} if decision.deny_reason else {},
        )


@dataclass(frozen=True)
class _SignalSpec:
    """An intermediate, consent-agnostic signal description from a builder."""

    task_class: str
    input: str
    output: str
    reward: float
    source_event_ids: tuple[object, ...] = ()
    fallback_id: str = "0"


# ---------------------------------------------------------------------------
# Per-event-type builders. Each reads ONLY PII-free contract fields and turns
# them into (input, output, reward, task_class). Ontology ids and bands are not
# PII; free text the platform may attach (e.g. a hint string) is scanned.
# ---------------------------------------------------------------------------


def _ontology_key(ontology: dict) -> str:
    """Stable, opaque description of an ontology location (no PII)."""
    parts = [f"topic={ontology.get('topic_id')}"]
    for k in ("outcome_id", "competency_id", "skill_id"):
        if ontology.get(k):
            parts.append(f"{k.split('_')[0]}={ontology[k]}")
    return " ".join(parts)


def _build_attempt(event: dict) -> list[_SignalSpec]:
    p = event["payload"]
    ont = _ontology_key(p["ontology"])
    # An attempt is a mastery-prediction signal: from the attempt context,
    # predict whether the learner answered correctly (reward = correctness).
    reward = 1.0 if p.get("correct") else 0.0
    inp = (
        f"task=predict-correct difficulty={p.get('difficulty')} "
        f"assistance={p.get('assistance_level')} mode={p.get('mode')} {ont}"
    )
    out = "correct" if p.get("correct") else "incorrect"
    return [
        _SignalSpec(
            task_class=TASK_MASTERY_PREDICT,
            input=inp,
            output=out,
            reward=reward,
            fallback_id=str(p.get("attempt_id")),
        )
    ]


def _build_score(event: dict) -> list[_SignalSpec]:
    p = event["payload"]
    ont = _ontology_key(p["ontology"])
    # Only HUMAN-FINAL, high-confidence scores are clean mastery-prediction
    # targets; low-confidence machine scores are weak reward and curate may drop.
    band = p.get("confidence_band", "low")
    reward = float(p.get("raw_score", 0.0))
    inp = f"task=predict-score mode={p.get('mode')} {ont}"
    out = f"score_band={'high' if reward >= 0.66 else 'mid' if reward >= 0.33 else 'low'}"
    return [
        _SignalSpec(
            task_class=TASK_MASTERY_PREDICT,
            input=inp,
            output=out,
            reward=reward if (p.get("human_final") and band != "low") else reward * 0.5,
            fallback_id=str(p.get("score_id")),
        )
    ]


def _build_mastery(event: dict) -> list[_SignalSpec]:
    p = event["payload"]
    ont = _ontology_key(p["ontology"])
    reading = p.get("reading", {})
    specs: list[_SignalSpec] = []
    # Mastery-band prediction signal.
    specs.append(
        _SignalSpec(
            task_class=TASK_MASTERY_PREDICT,
            input=f"task=predict-band {ont}",
            output=f"band={reading.get('band')}",
            reward=float(reading.get("composite", 0.0)),
            source_event_ids=tuple(p.get("source_event_ids", [])),
            fallback_id=str(reading.get("band", "band")),
        )
    )
    # Gap-classification signals: each confirmed gap is a labelled example.
    for i, gap in enumerate(p.get("gaps", [])):
        if not gap.get("confirmed"):
            continue  # only corroborated gaps are clean labels
        specs.append(
            _SignalSpec(
                task_class=TASK_GAP_CLASSIFY,
                input=f"task=classify-gap {ont} rationale={_safe(gap.get('rationale', ''))}",
                output=f"gap={gap.get('gap_type')}",
                reward=float(gap.get("confidence", 0.0)),
                source_event_ids=tuple(gap.get("evidence_event_ids", [])),
                fallback_id=f"gap{i}",
            )
        )
    return specs


def _safe(text: str) -> str:
    """Trim free text so a rationale can be embedded without PII risk; the
    LearningSignal constructor still scans it."""
    return text.replace("\n", " ").strip()[:240]


_BUILDERS = {
    "attempt.recorded": _build_attempt,
    "score.recorded": _build_score,
    "mastery.updated": _build_mastery,
}
