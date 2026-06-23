"""The Track-1 frontier TEACHER (Gemini) distillation seam (spine A4 — Track 2).

Distillation needs TARGETS: for a student input we want the teacher's high-quality
output to imitate. Two kinds of target feed the foundry:

1. VERIFIED Track-1 OUTPUTS already produced + passed through the fabric's
   generate-and-verify gate. These are free, on-policy, and PII-free by
   construction; they are turned directly into distillation examples — no live
   call needed (this path is always available, even offline).
2. TEACHER-AUGMENTED targets: where coverage is thin (a gap type the student has
   few examples of), the teacher (Gemini, Track 1) is asked to produce a
   rubric-grounded target. This is the live path.

INVARIANT 4 — the teacher key is read BY NAME from the AI fabric's env var
(``CLSS_AIFABRIC_DEV_GEMINI_API_KEY``); it is sent only in the ``x-goog-api-key``
header at call time, never stored on an instance, never logged, never returned.

INVARIANT 11 — the teacher is a Track-1 LABEL used as a distillation SOURCE only.
No Track-1 credential is conflated with a Track-2 artifact; the foundry only ever
emits Track-2 students.

DEGRADES CLEANLY — with no key OR no ``httpx`` OR a provider/parse error, the
teacher path returns a clearly-marked unavailable result and the foundry falls
back to verified Track-1 outputs alone. It NEVER fabricates a teacher target.

INVARIANT 1/2 — every prompt is built from PII-free fields and every produced
target is re-scanned by :func:`assert_pii_free`; a leak drops the example rather
than letting it enter a dataset.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Protocol

from .capture import (
    TASK_GAP_CLASSIFY,
    LearningSignal,
    PiiLeakError,
    assert_pii_free,
)
from .config import TEACHER_KEY_ENV_VAR, TEACHER_KEY_SECRET_NAME, Settings, get_settings
from .rubrics import GAP_RUBRICS, is_gap_type, taxonomy_prompt_block

# The Track-1 teacher model LABEL (distillation source only; never a credential).
TEACHER_MODEL_LABEL = "gemini-2.0-flash"

# Gemini generateContent endpoint (HTTPS). The key rides in a header at call
# time, never in the URL, mirroring the AI fabric / governance providers.
_GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)

TRACK_ID = 2


@dataclass(frozen=True)
class TeacherTarget:
    """A single PII-free distillation target proposed by the teacher.

    ``output`` is the imitation target for ``input`` on ``task_class``;
    ``confidence`` is the teacher's self-reported confidence in [0,1]. A target
    only becomes a positive training example after curation's verify gate.
    """

    task_class: str
    input: str
    output: str
    confidence: float
    teacher_label: str = TEACHER_MODEL_LABEL


@dataclass(frozen=True)
class TeacherResult:
    """The outcome of a teacher distillation request.

    ``available`` is False when the teacher degraded (no key / no httpx / error);
    in that case ``targets`` is empty and ``reason`` explains why, so the caller
    falls back to verified Track-1 outputs without ever fabricating a target.
    """

    available: bool
    targets: tuple[TeacherTarget, ...]
    reason: str
    teacher_label: str = TEACHER_MODEL_LABEL
    track: int = TRACK_ID  # the STUDENT being distilled is always Track 2


# ---------------------------------------------------------------------------
# The provider seam (real httpx by default; injectable for offline tests)
# ---------------------------------------------------------------------------


class TeacherProvider(Protocol):
    """The seam the teacher calls through.

    A real implementation posts to Gemini over httpx using the raw key (received
    here and NEVER returned or logged) and returns parsed targets. Injected in
    tests so the teacher is exercised entirely OFFLINE.
    """

    def propose(
        self, *, raw_key: str, model_label: str, prompt: str
    ) -> list[dict]:
        ...


@dataclass
class GeminiTeacherProvider:
    """A REAL Track-1 teacher backed by Gemini generateContent over HTTPS (httpx).

    The raw key is supplied at call time and sent in the ``x-goog-api-key``
    header — never in the URL, never logged. The response is parsed into a list
    of ``{task_class, input, output, confidence}`` dicts; a malformed/empty
    response raises so the live teacher degrades cleanly (never fabricates).
    """

    timeout_seconds: float = 20.0

    def propose(self, *, raw_key: str, model_label: str, prompt: str) -> list[dict]:
        import httpx  # imported lazily so the module stays import-safe with no httpx

        url = _GEMINI_ENDPOINT.format(model=model_label)
        payload = {
            "system_instruction": {"parts": [{"text": _SYSTEM_INSTRUCTION}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.0,
                "responseMimeType": "application/json",
            },
        }
        resp = httpx.post(
            url,
            headers={"x-goog-api-key": raw_key, "content-type": "application/json"},
            json=payload,
            timeout=self.timeout_seconds,
        )
        resp.raise_for_status()
        return _parse_gemini_targets(resp.json())


_SYSTEM_INSTRUCTION = (
    "You are an expert tutor acting as a DISTILLATION TEACHER for a small edge "
    "model. For each requested learning-gap type, produce one concise, correct "
    "tutor RESPONSE that matches the gap's rubric. Use NEUTRAL examples only: "
    "never invent a person's name, contact detail, school, or brand. Reply with "
    'STRICT JSON only: {"targets": [{"task_class": <str>, "input": <str>, '
    '"output": <str>, "confidence": <number 0..1>}]}. Never explain.'
)


def _parse_gemini_targets(body: dict) -> list[dict]:
    """Parse a Gemini ``generateContent`` body into target dicts.

    Raises on a malformed/empty response so the caller degrades to the
    deterministic fallback rather than fabricating a teacher target.
    """
    candidates = body.get("candidates") or []
    parts = (candidates[0].get("content") or {}).get("parts") or []
    raw_text = "".join(p.get("text", "") for p in parts).strip()
    if not raw_text:
        raise ValueError("empty teacher response")
    parsed = json.loads(raw_text)
    targets = parsed.get("targets") if isinstance(parsed, dict) else None
    if not isinstance(targets, list):
        raise ValueError("teacher response missing a targets list")
    return targets


# ---------------------------------------------------------------------------
# Verified Track-1 outputs -> distillation examples (always-available path)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VerifiedTrack1Output:
    """A Track-1 output that already PASSED the fabric's generate-and-verify gate.

    PII-free by construction (carries only opaque refs + neutral text). It is
    turned into a distillation example without any live call — the teacher's work
    was already done and verified on-policy.
    """

    task_class: str
    input: str
    output: str
    verify_confidence: float
    canonical_uuid: object  # opaque UUID — never PII
    consent_ref: object  # opaque UUID — never PII
    age_tier: str | None = None
    source_event_id: object | None = None


def signals_from_verified_outputs(
    outputs: list[VerifiedTrack1Output],
    *,
    consent_gate,
) -> list[LearningSignal]:
    """Turn verified Track-1 outputs into consent-stamped LearningSignals.

    Each output is admitted ONLY if the consent gate permits the learner's data
    for model improvement (INVARIANT 6) and the text is PII-free (INVARIANT 1/2);
    an unverified or inadmissible output never becomes a positive target. The
    verify stamp is carried so curate honours it directly.
    """
    out: list[LearningSignal] = []
    for i, vo in enumerate(outputs):
        # PII defence in depth — a leak drops this example, never aborts the run.
        try:
            assert_pii_free(vo.input, where="teacher.input")
            assert_pii_free(vo.output, where="teacher.output")
        except PiiLeakError:
            continue
        decision = consent_gate.evaluate(
            canonical_uuid=vo.canonical_uuid, consent_ref=vo.consent_ref
        )
        sid = f"verified:{vo.task_class}:{vo.source_event_id or i}"
        out.append(
            LearningSignal(
                signal_id=sid,
                canonical_uuid=vo.canonical_uuid,  # type: ignore[arg-type]
                task_class=vo.task_class,
                input=vo.input,
                output=vo.output,
                reward=float(vo.verify_confidence),
                consent_ref=vo.consent_ref,  # type: ignore[arg-type]
                age_tier=decision.age_tier,
                admissible=decision.admissible,
                source_event_ids=((vo.source_event_id,) if vo.source_event_id else ()),  # type: ignore[arg-type]
                verify_passed=True,
                verify_confidence=float(vo.verify_confidence),
                meta=(
                    {"deny_reason": decision.deny_reason.value}
                    if decision.deny_reason
                    else {"source": "verified-track1"}
                ),
            )
        )
    return out


# ---------------------------------------------------------------------------
# The teacher (live or degraded)
# ---------------------------------------------------------------------------


class DistillationTeacher:
    """Builds rubric-grounded distillation targets from the Track-1 teacher.

    Holds no credentials of its own: it reads the named teacher key from settings
    only at the moment it must call the provider, and never returns or logs it.
    With no key OR no provider seam, every entrypoint degrades to a clearly-marked
    unavailable result — it never fabricates a teacher target.
    """

    def __init__(
        self,
        *,
        provider: TeacherProvider | None = None,
        settings: Settings | None = None,
        model_label: str = TEACHER_MODEL_LABEL,
    ) -> None:
        self._provider = provider
        self._settings = settings or get_settings()
        self._model_label = model_label

    def __repr__(self) -> str:
        # Never let the settings' raw key reach a repr / log line.
        return (
            f"DistillationTeacher(model_label={self._model_label!r}, "
            f"provider={'present' if self._provider is not None else 'absent'}, "
            f"key={'present' if self._settings.teacher_configured() else 'absent'})"
        )

    def live_available(self) -> bool:
        """True only when a key is present AND a provider seam is wired."""
        return self._settings.teacher_configured() and self._provider is not None

    def _unavailable_reason(self) -> str:
        if not self._settings.teacher_configured():
            return (
                f"teacher key unset: set secret '{TEACHER_KEY_SECRET_NAME}' via env "
                f"var '{TEACHER_KEY_ENV_VAR}'; falling back to verified Track-1 outputs"
            )
        return "no teacher provider seam wired; falling back to verified Track-1 outputs"

    def propose_for_gaps(self, gap_types: list[str]) -> TeacherResult:
        """Ask the teacher for one rubric-grounded target per requested gap type.

        Only in-taxonomy gap types are requested. With no live path, returns an
        unavailable result (empty targets) — the foundry then trains on verified
        Track-1 outputs alone, never on a fabricated teacher target.
        """
        wanted = [g for g in gap_types if is_gap_type(g)]
        if not wanted:
            return TeacherResult(available=False, targets=(), reason="no in-taxonomy gap types requested")

        if not self.live_available():
            return TeacherResult(available=False, targets=(), reason=self._unavailable_reason())

        raw_key = self._settings.teacher_key
        prompt = self._build_prompt(wanted)
        try:
            raw_targets = self._provider.propose(  # type: ignore[union-attr]
                raw_key=raw_key,  # type: ignore[arg-type]
                model_label=self._model_label,
                prompt=prompt,
            )
        except Exception as exc:  # noqa: BLE001 — any provider/transport error degrades
            # Never include the raw key or provider internals; report only the type.
            return TeacherResult(
                available=False,
                targets=(),
                reason=f"teacher call failed ({type(exc).__name__}); degraded to fallback",
            )

        targets = self._sanitise(raw_targets, wanted)
        if not targets:
            return TeacherResult(
                available=False, targets=(), reason="teacher returned no usable targets"
            )
        return TeacherResult(available=True, targets=tuple(targets), reason="teacher targets produced")

    def signals_from_targets(
        self,
        result: TeacherResult,
        *,
        canonical_uuid,
        consent_ref,
        consent_gate,
    ) -> list[LearningSignal]:
        """Stamp teacher targets as consent-gated LearningSignals.

        Teacher targets are SYNTHETIC (no learner produced them), so they ride a
        single supplied opaque canonical_uuid/consent_ref for provenance and are
        gated like any other signal (INVARIANT 6). PII-free (INVARIANT 1/2).
        """
        decision = consent_gate.evaluate(
            canonical_uuid=canonical_uuid, consent_ref=consent_ref
        )
        out: list[LearningSignal] = []
        for i, t in enumerate(result.targets):
            out.append(
                LearningSignal(
                    signal_id=f"teacher:{t.task_class}:{i}",
                    canonical_uuid=canonical_uuid,
                    task_class=t.task_class,
                    input=t.input,
                    output=t.output,
                    reward=t.confidence,
                    consent_ref=consent_ref,
                    age_tier=decision.age_tier,
                    admissible=decision.admissible,
                    verify_passed=None,  # teacher targets still face the verify gate
                    verify_confidence=None,
                    meta={"source": "teacher", "teacher_label": t.teacher_label},
                )
            )
        return out

    def _build_prompt(self, gap_types: list[str]) -> str:
        block = taxonomy_prompt_block()
        wanted = ", ".join(gap_types)
        return (
            f"{block}\n\n"
            f"For each of these gap types: {wanted}\n"
            f"emit one target whose task_class is '{TASK_GAP_CLASSIFY}', whose input "
            f"describes a NEUTRAL learner situation exhibiting that gap (no names, no "
            f"contact details, no brands), and whose output is the gap type token. "
            f"Return the strict JSON now."
        )

    def _sanitise(self, raw_targets: list[dict], wanted: list[str]) -> list[TeacherTarget]:
        """Validate + PII-scrub teacher targets; drop anything off-taxonomy/unsafe."""
        wanted_set = set(wanted)
        out: list[TeacherTarget] = []
        seen: set[str] = set()
        for rt in raw_targets:
            if not isinstance(rt, dict):
                continue
            task_class = str(rt.get("task_class", "")) or TASK_GAP_CLASSIFY
            inp = str(rt.get("input", ""))
            output = str(rt.get("output", ""))
            if not inp or not output:
                continue
            # Gap-classification targets must carry an in-taxonomy, requested label.
            if task_class == TASK_GAP_CLASSIFY:
                if output not in GAP_RUBRICS or output not in wanted_set:
                    continue
                if output in seen:  # one target per gap type — keep it balanced
                    continue
            try:
                assert_pii_free(inp, where="teacher.target.input")
                assert_pii_free(output, where="teacher.target.output")
            except PiiLeakError:
                continue
            try:
                conf = float(rt.get("confidence", 0.0))
            except (TypeError, ValueError):
                conf = 0.0
            conf = max(0.0, min(1.0, conf))
            seen.add(output)
            out.append(
                TeacherTarget(
                    task_class=task_class,
                    input=inp,
                    output=output,
                    confidence=conf,
                    teacher_label=self._model_label,
                )
            )
        return out


def make_teacher(
    *,
    settings: Settings | None = None,
    env: dict[str, str] | None = None,
    provider: TeacherProvider | None = None,
) -> DistillationTeacher:
    """Construct a teacher; wire the REAL Gemini provider whenever a key is present.

    With a key, the live httpx-backed provider is wired so the teacher can produce
    rubric-grounded targets. With no key, no provider is wired and the teacher
    degrades to verified-outputs-only — importing this module makes no live call.
    """
    s = settings or get_settings(env)
    if provider is None and s.teacher_configured():
        provider = GeminiTeacherProvider()
    return DistillationTeacher(provider=provider, settings=s)
