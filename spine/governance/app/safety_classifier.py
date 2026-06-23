"""The LIVE child-safety classifier (spine A7, Track 1 capability).

The child-safety subsystem (:mod:`app.child_safety`) screens EVERY free-text
surface for moderation (harassment / sexual / hate / violence) and CRISIS
(self-harm / abuse / immediate danger). This module binds that subsystem to a
REAL moderation/crisis classifier — Gemini, reached over HTTPS — while keeping
the always-on deterministic lexicon screen as the fallback when no provider is
available.

INVARIANT 4 — SECRETS ARE ENV-ONLY, READ BY NAME, NEVER HARDCODED. The raw
Gemini key is read by NAME from the environment (secret
``clss.aifabric.dev.gemini_api_key`` -> OS env ``CLSS_AIFABRIC_DEV_GEMINI_API_KEY``)
only at the moment the provider is called. It is NEVER hardcoded, NEVER returned,
NEVER logged, and NEVER placed in any result.

INVARIANT 7 — GENERATE-AND-VERIFY / FAIL TOWARD REVIEW. The live model can only
ADD safety signals; it can NEVER subtract them. The deterministic on-device
screen is the always-on floor: its verdict is unioned with the live verdict, so
a crisis or a flag the rules catch is preserved even if the model misses it. A
crisis is NEVER silenced — on a missing key, a provider error, a timeout, or a
malformed response, the deterministic crisis/flag still stands and escalates.

INVARIANT 11 — TWO TRACKS ARE NEVER CONFLATED. This is a Track 1 (external LLM
routing) capability. It uses Track 1's own named Gemini secret and never borrows
Track 2's endpoint key.

INVARIANT 1/2/12 — NO PII. The classifier returns only
``(categories, crisis, confidence)``; it never writes the screened text, the raw
key, or any author identifier into a result, a log, or a behavioral store.

DEGRADES CLEANLY — when the key is unset OR ``httpx`` is absent, the live path is
clearly UNAVAILABLE and the subsystem runs on the deterministic floor alone. No
network is required to import or test this module; tests inject a fake provider
and never make a live call.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Protocol

from .child_safety import (
    DeterministicSafetyClassifier,
    SafetyClassifier,
)

logger = logging.getLogger("clss.governance.child_safety.classifier")

# ---------------------------------------------------------------------------
# The named secret (NAME ONLY — never a value). Mapped OS env key below.
# ---------------------------------------------------------------------------

# Track 1 Gemini provider key. Read by NAME from the environment.
GEMINI_KEY_SECRET_NAME = "clss.aifabric.dev.gemini_api_key"
GEMINI_KEY_ENV_VAR = "CLSS_AIFABRIC_DEV_GEMINI_API_KEY"

# This classifier is Track 1 (external LLM routing) — never conflated with Track 2.
TRACK_ID = 1

# The moderation/crisis model label routed on Track 1. A label only; the call is
# made by the provider seam when present.
GEMINI_MODEL_LABEL = "gemini-2.0-flash"

# Gemini generateContent endpoint (HTTPS). The key is passed by header at call
# time; it is NEVER embedded in this URL or logged.
_GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent"
)

# Moderation categories the subsystem recognises. The live model is constrained
# to this closed set so its output maps onto the same verdict ladder the
# deterministic screen uses.
_KNOWN_CATEGORIES = ("harassment", "hate", "violence", "sexual", "self-harm")

# The instruction handed to the model. It returns STRICT JSON only — no free
# text, no echo of the input — so nothing the learner wrote can leak back.
_SYSTEM_INSTRUCTION = (
    "You are a child-safety classifier for text written by minors. "
    "Classify the message for these moderation categories only: "
    "harassment, hate, violence, sexual, self-harm. "
    "Separately decide if it is a CRISIS: a self-harm, suicide, abuse, or "
    "immediate-danger signal that requires a human. "
    "When in doubt, flag it — never under-report a crisis. "
    "Respond with STRICT JSON and nothing else, of the exact shape: "
    '{"categories": ["..."], "crisis": true|false, "confidence": 0.0} . '
    "Do not include the input text or any commentary in your response."
)


# ---------------------------------------------------------------------------
# The provider seam (an HTTPS Gemini call by default; injectable for tests)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClassifierVerdict:
    """A classifier's verdict on a free-text message.

    Carries ONLY a closed-set category list, a crisis flag, and a confidence in
    [0, 1]. Never the screened text, never the raw key, never an author ref.
    """

    categories: tuple[str, ...]
    crisis: bool
    confidence: float


class ModerationProvider(Protocol):
    """The Track 1 seam for one moderation/crisis inference call.

    A real implementation calls an external provider over HTTPS, given the raw
    key alone at call time. The raw key NEVER leaves this seam; the provider
    returns only a :class:`ClassifierVerdict`. With no seam wired, the live
    classifier degrades to the deterministic floor and never fabricates a result.
    """

    def classify(self, *, raw_key: str, model_label: str, text: str) -> ClassifierVerdict:
        ...


class GeminiModerationProvider:
    """A REAL moderation/crisis provider backed by Gemini over HTTPS (httpx).

    The raw key is supplied at call time and sent in the ``x-goog-api-key``
    header — never in the URL, never logged. The response is parsed into a
    closed-set :class:`ClassifierVerdict`; anything unparseable raises so the
    live classifier fails toward the deterministic floor (never toward silence).
    """

    def __init__(self, *, timeout_seconds: float = 6.0) -> None:
        self._timeout = timeout_seconds

    def classify(self, *, raw_key: str, model_label: str, text: str) -> ClassifierVerdict:
        import httpx  # imported lazily so the module stays import-safe with no httpx

        url = _GEMINI_ENDPOINT.format(model=model_label)
        payload = {
            "system_instruction": {"parts": [{"text": _SYSTEM_INSTRUCTION}]},
            "contents": [{"role": "user", "parts": [{"text": text}]}],
            "generationConfig": {
                "temperature": 0.0,
                "responseMimeType": "application/json",
            },
        }
        # The key travels in a header, by NAME-read value, over HTTPS only.
        resp = httpx.post(
            url,
            headers={"x-goog-api-key": raw_key, "content-type": "application/json"},
            json=payload,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return _parse_gemini_response(resp.json())


def _parse_gemini_response(body: dict) -> ClassifierVerdict:
    """Parse a Gemini ``generateContent`` body into a closed-set verdict.

    Raises on a malformed/empty response so the caller fails toward the
    deterministic floor. Categories are clamped to the known set; confidence to
    the unit interval.
    """
    candidates = body.get("candidates") or []
    parts = (candidates[0].get("content") or {}).get("parts") or []
    raw_text = "".join(p.get("text", "") for p in parts).strip()
    if not raw_text:
        raise ValueError("empty classifier response")
    parsed = json.loads(raw_text)

    cats = tuple(
        c for c in parsed.get("categories", []) if c in _KNOWN_CATEGORIES
    )
    crisis = bool(parsed.get("crisis", False))
    try:
        confidence = float(parsed.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))
    return ClassifierVerdict(categories=cats, crisis=crisis, confidence=confidence)


# ---------------------------------------------------------------------------
# The live safety classifier (a SafetyClassifier the subsystem can use)
# ---------------------------------------------------------------------------


class LiveSafetyClassifier(SafetyClassifier):
    """A live moderation/crisis classifier (Gemini, Track 1) with a hard floor.

    Implements :class:`~app.child_safety.SafetyClassifier`, so the existing
    :class:`~app.child_safety.ChildSafetySubsystem` uses it unchanged. It runs
    the always-on deterministic screen FIRST, then — only when a key is present
    and a provider seam is wired — asks the live model and UNIONS the two
    results:

      * a crisis is true if EITHER path flags it (the live model can never
        silence the deterministic crisis),
      * the category set is the UNION of both,
      * confidence is the MAX of the two (a clear hit stays high-confidence).

    On a missing key, an absent ``httpx``, a provider error, or a malformed
    response, it returns the deterministic verdict alone — clearly degraded,
    never silent.
    """

    def __init__(
        self,
        *,
        provider: ModerationProvider | None = None,
        fallback: SafetyClassifier | None = None,
        model_label: str = GEMINI_MODEL_LABEL,
        env: dict[str, str] | None = None,
    ) -> None:
        # The deterministic on-device screen is the always-on floor.
        self._fallback = fallback or DeterministicSafetyClassifier()
        # Default to a real Gemini-over-HTTPS provider; tests inject a fake.
        self._provider = provider if provider is not None else GeminiModerationProvider()
        self._model_label = model_label
        # Inject env for tests; default to the process environment. We read the
        # key by NAME only, at call time.
        self._env = env if env is not None else os.environ
        self.name = self._compose_name()

    # -- internal: the raw key, by NAME, never exposed --------------------

    def _raw_key(self) -> str | None:
        """The raw Gemini key, or ``None``. PRIVATE — never returned/logged."""
        value = self._env.get(GEMINI_KEY_ENV_VAR)
        if value is None or not str(value).strip():
            return None
        return str(value)

    def live_available(self) -> bool:
        """True only when a key is present AND a provider seam is wired."""
        return self._raw_key() is not None and self._provider is not None

    def _compose_name(self) -> str:
        if self.live_available():
            return f"gemini-live-classifier ({self._model_label}) + deterministic floor"
        return (
            "deterministic-lexicon-screen (Gemini classifier UNAVAILABLE — "
            f"set env var '{GEMINI_KEY_ENV_VAR}' / secret '{GEMINI_KEY_SECRET_NAME}')"
        )

    # -- the classification (returns ONLY categories, crisis, confidence) --

    def classify(self, text: str) -> tuple[tuple[str, ...], bool, float]:
        # ALWAYS run the deterministic floor first. Its result can only be
        # added to, never removed — a crisis it catches is never silenced.
        base_cats, base_crisis, base_conf = self._fallback.classify(text)

        raw_key = self._raw_key()
        if raw_key is None or self._provider is None:
            # No live path: run on the deterministic floor alone (degraded).
            return base_cats, base_crisis, base_conf

        try:
            verdict = self._provider.classify(
                raw_key=raw_key, model_label=self._model_label, text=text
            )
        except Exception:
            # A provider error must NEVER silence a crisis: keep the floor.
            logger.warning(
                "live child-safety classifier unavailable; falling back to the "
                "deterministic screen (crisis/flags preserved)."
            )
            return base_cats, base_crisis, base_conf

        # UNION the live verdict with the deterministic floor.
        crisis = base_crisis or bool(verdict.crisis)
        merged: list[str] = list(base_cats)
        for c in verdict.categories:
            if c in _KNOWN_CATEGORIES and c not in merged:
                merged.append(c)
        # A detected crisis implies the self-harm moderation category, matching
        # the deterministic screen's behaviour.
        if crisis and "self-harm" not in merged:
            merged.append("self-harm")
        confidence = max(base_conf, float(verdict.confidence))
        confidence = max(0.0, min(1.0, confidence))
        return tuple(merged), crisis, confidence


# ---------------------------------------------------------------------------
# The factory — wires the live classifier into the subsystem by config
# ---------------------------------------------------------------------------


def make_safety_classifier(
    *,
    provider: ModerationProvider | None = None,
    fallback: SafetyClassifier | None = None,
    env: dict[str, str] | None = None,
) -> SafetyClassifier:
    """Return the classifier the child-safety subsystem should use.

    ALWAYS returns a classifier whose deterministic floor is active. When the
    Gemini key is present (by NAME) and a provider seam is available, the live
    Gemini path is layered ON TOP of that floor; otherwise the subsystem runs on
    the deterministic screen alone (clearly degraded, never silent).

    ``provider`` / ``env`` may be injected for tests and real wiring. The raw key
    is never returned.
    """
    return LiveSafetyClassifier(provider=provider, fallback=fallback, env=env)
