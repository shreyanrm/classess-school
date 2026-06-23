"""Hyperlocalize VERIFIED content for a locale — relevance, not translation (B3).

Hyperlocalization delivers the SAME concept differently for THIS board, language,
region, calendar and culture. It is not translation: worked examples, the names
of places, the units, and the festivals-aware calendar references adapt to the
reader's world and language, while the SUBJECT TERMINOLOGY is preserved verbatim
(photosynthesis stays photosynthesis) and the underlying concept and its
correctness never change.

This module sits AFTER generation and BEFORE service. It runs THROUGH the same
generate-and-verify path as everything else (INVARIANT 7 — nothing served
unverified): a localised variant is only served when it passes a confidence
gate whose DETERMINISTIC checks confirm two non-negotiables —

  1. every subject term present in the base content is still present verbatim in
     the localised variant (no subject term was translated away), and
  2. the load-bearing, checkable facts of the concept are unchanged (e.g. a
     math item's expression + answer are identical), so localisation cannot
     silently alter correctness.

Degrades gracefully: with NO localisation provider wired, it returns the BASE
content marked ``not_yet_localised`` (never a fabricated translation). Board is a
FIELD on ``LocaleContext`` (a label, never an enum of permitted boards), derived
from the institution's language/region/calendar hyperlocalization policy keys
(``locale.language`` / ``locale.region`` / ``locale.calendar`` in
``modules/institution/app/policy.py``).

No PII, no secrets, no board lock-in. The live provider key is owned by the
ai-fabric router (``clss.aifabric.dev.track1_provider_key``); this module names
no key of its own and holds no credentials (INVARIANT 8 — agents hold no creds).
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Mapping, Protocol, Sequence

from . import _spine


# ---------------------------------------------------------------------------
# Locale context — derived from institution hyperlocalization policy
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LocaleContext:
    """The locale a piece of content is hyperlocalised FOR.

    ``board`` is a FIELD — a plain label for the board this delivery targets,
    never an enum of permitted boards (no board lock-in). The other fields mirror
    the three well-known hyperlocalization policy keys resolved on the
    institution hierarchy (``locale.language`` / ``locale.region`` /
    ``locale.calendar``), plus an optional ``culture`` handle. Any field may be
    ``None`` — this module never invents a locale default.
    """

    board: str | None = None       # board label (a field; never a lock-in enum)
    language: str | None = None     # reader's language, e.g. an IETF/ISO code
    region: str | None = None       # jurisdiction/region label
    calendar: str | None = None     # academic-calendar handle (festival-aware)
    culture: str | None = None      # optional culture handle for examples/tone

    @property
    def is_specified(self) -> bool:
        """True when at least one locale dimension is set to drive adaptation."""
        return any((self.board, self.language, self.region, self.calendar, self.culture))

    def as_signal(self) -> dict[str, str]:
        """A plain dict of the set dimensions, for the provider and the trace."""
        out: dict[str, str] = {}
        for name in ("board", "language", "region", "calendar", "culture"):
            value = getattr(self, name)
            if value is not None:
                out[name] = str(value)
        return out


# ---------------------------------------------------------------------------
# Subject-term preservation
# ---------------------------------------------------------------------------

def _word_present(term: str, text: str) -> bool:
    """True when ``term`` appears verbatim in ``text`` as a whole word/phrase.

    Case-insensitive on the boundary match but the COMPARISON that the gate
    enforces is verbatim casing (see :func:`subject_terms_preserved`); this is
    only the presence probe.
    """
    if not term:
        return True
    pattern = r"(?<![\w-])" + re.escape(term) + r"(?![\w-])"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def _gather_text(body: Mapping[str, object]) -> str:
    """Flatten the string-valued leaves of a content body into one search blob."""
    parts: list[str] = []

    def walk(value: object) -> None:
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, Mapping):
            for v in value.values():
                walk(v)
        elif isinstance(value, (list, tuple)):
            for v in value:
                walk(v)

    walk(body)
    return "\n".join(parts)


def subject_terms_preserved(
    *,
    subject_terms: Sequence[str],
    base_body: Mapping[str, object],
    localized_body: Mapping[str, object],
) -> tuple[bool, list[str]]:
    """Check every subject term is preserved VERBATIM in the localised body.

    Returns ``(ok, violations)``. A term counts as preserved when it appears in
    the localised body with the SAME casing wherever it appeared in the base.
    Terms not present in the base are ignored (nothing to preserve). This is the
    "preserve subject terminology verbatim" law made checkable.
    """
    base_text = _gather_text(base_body)
    local_text = _gather_text(localized_body)
    violations: list[str] = []
    for term in subject_terms:
        if not term:
            continue
        in_base = re.search(r"(?<![\w-])" + re.escape(term) + r"(?![\w-])", base_text)
        if in_base is None:
            continue  # term not in base content; nothing to preserve
        # Must survive verbatim (exact casing) in the localised body.
        survived = re.search(r"(?<![\w-])" + re.escape(term) + r"(?![\w-])", local_text)
        if survived is None:
            violations.append(term)
    return (not violations, violations)


# ---------------------------------------------------------------------------
# Concept / correctness preservation
# ---------------------------------------------------------------------------

# The keys whose values are load-bearing for correctness. If a base body carries
# any of these, the localised body MUST carry the identical value — localisation
# adapts the surface, never the answer.
_CORRECTNESS_KEYS = ("expression", "answer", "unit", "claimed_answer", "result")


def concept_unchanged(
    *,
    base_body: Mapping[str, object],
    localized_body: Mapping[str, object],
) -> tuple[bool, list[str]]:
    """Check the localised body did not alter any correctness-bearing fact.

    Returns ``(ok, violations)``. For every correctness key present in the base
    body, the localised body must carry the identical value. A localisation that
    changes a math answer or its units fails this check and is withheld.
    """
    violations: list[str] = []
    for key in _CORRECTNESS_KEYS:
        if key in base_body:
            if localized_body.get(key) != base_body.get(key):
                violations.append(key)
    return (not violations, violations)


# ---------------------------------------------------------------------------
# Localisation provider
# ---------------------------------------------------------------------------

class LocalizationProvider(Protocol):
    """Produces a localised variant of a verified content body for a locale.

    A live implementation is an ai-fabric Track-1 capability behind the router's
    provider key; this module never holds that key. With NO provider wired the
    hyperlocalizer degrades to returning the base content marked
    ``not_yet_localised`` — it never fabricates a translation.
    """

    def localize(
        self,
        *,
        body: Mapping[str, object],
        locale: LocaleContext,
        subject_terms: Sequence[str],
    ) -> dict[str, object]:
        ...


# ---------------------------------------------------------------------------
# Result shapes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HyperlocalizationOutcome:
    """The outcome of a hyperlocalization attempt.

    ``localized`` is True only when a variant PASSED the confidence gate (subject
    terms verbatim, concept unchanged, gate satisfied) and was served. Otherwise
    ``body`` is the safe fallback: the BASE content, marked ``not_yet_localised``,
    with ``review_reason`` explaining why (no provider, or the variant was
    withheld). Either way ``body`` is safe to serve — it is always verified
    content, never a fabricated localisation.
    """

    localized: bool
    body: dict[str, object]
    locale: LocaleContext
    request_id: str
    provider_available: bool
    not_yet_localised: bool
    review_reason: str | None = None
    confidence: float | None = None
    gate_threshold: float | None = None
    verification: object | None = None


def _mark_not_yet_localised(
    body: Mapping[str, object], locale: LocaleContext
) -> dict[str, object]:
    """Return a copy of the base body marked as awaiting localisation."""
    out = dict(body)
    out["hyperlocalization"] = {
        "localized": False,
        "not_yet_localised": True,
        "locale": locale.as_signal(),
    }
    return out


def _mark_localised(
    body: Mapping[str, object], locale: LocaleContext, *, confidence: float
) -> dict[str, object]:
    """Return a copy of a localised body marked as verified-localised."""
    out = dict(body)
    out["hyperlocalization"] = {
        "localized": True,
        "not_yet_localised": False,
        "locale": locale.as_signal(),
        "confidence": confidence,
    }
    return out


def _new_request_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Deterministic localisation checks (the generate-and-verify deterministic step)
# ---------------------------------------------------------------------------

def localization_deterministic_checks(
    *,
    candidate_body: Mapping[str, object],
    base_body: Mapping[str, object],
    subject_terms: Sequence[str],
) -> list:
    """The DETERMINISTIC checks the gate runs FIRST over a localised variant.

    Returns spine ``DeterministicCheck`` results: subject terms preserved
    verbatim, and concept/correctness-bearing facts unchanged. These run before
    any second-model cross-check, mirroring the spine's deterministic-first
    ordering, and a failure keeps the gate closed (fail closed).
    """
    terms_ok, term_violations = subject_terms_preserved(
        subject_terms=subject_terms,
        base_body=base_body,
        localized_body=candidate_body,
    )
    concept_ok, concept_violations = concept_unchanged(
        base_body=base_body, localized_body=candidate_body
    )
    return [
        _spine.DeterministicCheck(  # type: ignore[attr-defined]
            "subject-terms-preserved-verbatim",
            terms_ok,
            "all subject terms survive verbatim"
            if terms_ok
            else f"subject terms translated away: {sorted(term_violations)}",
        ),
        _spine.DeterministicCheck(  # type: ignore[attr-defined]
            "concept-correctness-unchanged",
            concept_ok,
            "concept and correctness-bearing facts unchanged"
            if concept_ok
            else f"localisation altered correctness fields: {sorted(concept_violations)}",
        ),
    ]


# ---------------------------------------------------------------------------
# The hyperlocalizer
# ---------------------------------------------------------------------------

class Hyperlocalizer:
    """Hyperlocalizes verified content, serving only verified localised variants.

    Construct with an optional ``LocalizationProvider`` (the relevance engine)
    and an optional spine ``Orchestrator``. With no provider it degrades to
    returning the base content marked ``not_yet_localised``. With a provider it
    produces a candidate variant and runs it THROUGH the spine's
    generate-and-verify path; the variant is served only if the deterministic
    subject-term and concept checks pass and the gate is satisfied.
    """

    def __init__(
        self,
        provider: LocalizationProvider | None = None,
        gate: object | None = None,
        second_model: object | None = None,
    ) -> None:
        self._provider = provider
        self._spine_available = _spine.SPINE_AVAILABLE
        if not self._spine_available:  # pragma: no cover - spine genuinely absent
            self._gate = None
            self._second_model = None
            return
        self._gate = gate if gate is not None else _spine.ConfidenceGate()  # type: ignore[operator]
        # No live second model => abstain, which keeps the gate closed (fail
        # closed); inject an agreeing checker to serve a clean variant.
        self._second_model = (
            second_model if second_model is not None
            else _spine.AbstainingSecondModel()  # type: ignore[operator]
        )

    @property
    def provider_available(self) -> bool:
        return self._provider is not None

    def hyperlocalize(
        self,
        *,
        body: Mapping[str, object],
        locale: LocaleContext,
        subject_terms: Sequence[str] = (),
    ) -> HyperlocalizationOutcome:
        """Produce a hyperlocalised variant of ``body`` for ``locale``.

        Returns served localised content only when it passes the gate. Degrades
        to the base content marked ``not_yet_localised`` when no provider is
        wired, when the locale is unspecified, or when the variant is withheld.
        """
        request_id = _new_request_id()

        # Degrade: no provider, no locale, or no spine => base content, marked.
        if self._provider is None:
            return self._not_localised(
                body, locale, request_id, provider_available=False,
                review_reason=(
                    "no localisation provider wired; serving the base content "
                    "marked not-yet-localised (no fabricated translation)."
                ),
            )
        if not locale.is_specified:
            return self._not_localised(
                body, locale, request_id, provider_available=True,
                review_reason="no locale dimensions set; nothing to hyperlocalize.",
            )
        if self._gate is None:  # pragma: no cover - spine missing
            return self._not_localised(
                body, locale, request_id, provider_available=True,
                review_reason="verification substrate unavailable; cannot serve a localised variant.",
            )

        # Produce a candidate localised body from the provider. Its self-reported
        # confidence is the generator confidence; default high when unset.
        candidate_body = dict(
            self._provider.localize(
                body=body, locale=locale, subject_terms=subject_terms
            )
        )
        generator_confidence = _candidate_confidence(candidate_body)

        # GENERATE-AND-VERIFY: deterministic checks FIRST (subject terms verbatim,
        # concept/correctness unchanged), then the second-model cross-check, then
        # the confidence gate. Served only when ALL conditions hold (INVARIANT 7).
        det_checks = localization_deterministic_checks(
            candidate_body=candidate_body,
            base_body=body,
            subject_terms=subject_terms,
        )
        agrees, sm_conf = self._second_model.cross_check(  # type: ignore[union-attr]
            task_class="content", content=candidate_body
        )
        confidence = min(generator_confidence, sm_conf)
        verification = self._gate.evaluate(det_checks, agrees, confidence)  # type: ignore[union-attr]

        if not verification.served:
            return self._not_localised(
                body, locale, request_id, provider_available=True,
                review_reason=verification.review_reason
                or "localised variant withheld by the confidence gate.",
                verification=verification,
            )

        return HyperlocalizationOutcome(
            localized=True,
            body=_mark_localised(
                candidate_body, locale, confidence=verification.confidence
            ),
            locale=locale,
            request_id=request_id,
            provider_available=True,
            not_yet_localised=False,
            review_reason=None,
            confidence=verification.confidence,
            gate_threshold=verification.gate_threshold,
            verification=verification,
        )

    def _not_localised(
        self,
        body: Mapping[str, object],
        locale: LocaleContext,
        request_id: str,
        *,
        provider_available: bool,
        review_reason: str | None,
        verification: object | None = None,
    ) -> HyperlocalizationOutcome:
        return HyperlocalizationOutcome(
            localized=False,
            body=_mark_not_yet_localised(body, locale),
            locale=locale,
            request_id=request_id,
            provider_available=provider_available,
            not_yet_localised=True,
            review_reason=review_reason,
            verification=verification,
        )


# ---------------------------------------------------------------------------
# Candidate confidence
# ---------------------------------------------------------------------------

# A provider MAY embed its self-reported localisation confidence under this key
# in the candidate body. It is stripped before the body is served (it is a
# verification signal, not learner-facing content).
_CONFIDENCE_KEY = "_localization_confidence"


def _candidate_confidence(candidate_body: dict[str, object]) -> float:
    """Read (and remove) the provider's self-reported confidence from a candidate.

    Defaults to a high confidence when the provider reports none, so a clean
    variant is gated by the second-model cross-check and the deterministic checks
    rather than spuriously failing on a missing confidence signal.
    """
    raw = candidate_body.pop(_CONFIDENCE_KEY, None)
    if raw is None:
        return 0.99
    try:
        return float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return 0.99
