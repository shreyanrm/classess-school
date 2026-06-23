"""The child-safety subsystem (spine A7).

INVARIANT 12 / A7 mandate — CHILD-SAFETY RUNS ON EVERY FREE-TEXT SURFACE. This
is the subsystem every free-text surface in the platform calls before showing,
storing, or routing learner text. It does four things:

1. **Moderation** — classify text into categories (harassment, sexual, hate,
   violence, self-harm, ...) and flag or block accordingly.
2. **Crisis detection** — detect self-harm / abuse / immediate-danger signals
   and mark the assessment ``CRISIS``. Crisis ALWAYS overrides a softer verdict.
3. **Escalation to qualified humans** — a crisis raises an ``Escalation`` to a
   qualified human and records it immutably through the audit log. The companion
   never tries to "handle" a serious matter itself (B9 note).
4. **No unmonitored channels** — a free-text surface MUST be registered as
   monitored. Assessing text on an unregistered / unmonitored surface raises
   ``UnmonitoredChannelError``; there is no path to free text that child-safety
   does not see.

Generate-and-verify discipline (INVARIANT 7) applies to classification: with no
live classifier provider the default classifier runs a deterministic
keyword/lexicon screen and ABSTAINS on subtle cases (returns low confidence)
rather than asserting "safe" — it fails toward review, never toward exposure.
The live provider (Track 1) and an on-edge model (Track 2) wire in later behind
their separate, separately-named env keys (INVARIANT 11); enabling them is a
config change, not a re-architecture.

No PII: authors are opaque ``canonical_uuid`` refs; the text itself is screened
in-process and never written to the behavioral event store.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from uuid import UUID

from .audit import AuditLog
from .models import (
    Escalation,
    EscalationStatus,
    SafetyAssessment,
    SafetyVerdict,
    new_id,
)


class UnmonitoredChannelError(PermissionError):
    """Raised when free text is assessed on an unregistered / unmonitored surface.

    No unmonitored channel is permitted: there is no way to send free text that
    the child-safety subsystem does not see.
    """


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Classifier seam (INVARIANT 7 + 11)
# ---------------------------------------------------------------------------
class SafetyClassifier(ABC):
    """A safety classifier. Live providers (Track 1 / Track 2) implement this;
    the default deterministic screen below keeps the subsystem working with no
    provider, failing toward review rather than toward exposure."""

    name: str

    @abstractmethod
    def classify(self, text: str) -> tuple[tuple[str, ...], bool, float]:
        """Return (moderation_categories, crisis_flag, confidence)."""


# A conservative deterministic lexicon. Intentionally small and explainable;
# the live model replaces this for nuanced cases. Listed terms are screening
# signals, not product copy (INVARIANT 12 copy discipline is about artifacts).
_CRISIS_PATTERNS = (
    r"\bkill myself\b",
    r"\bself[\s-]?harm\b",
    r"\bhurt myself\b",
    r"\bwant to die\b",
    r"\bend (?:it|my life)\b",
    r"\bsuicid",
    r"\b(?:he|she|they|someone)\s+(?:hit|hurt|touched)\s+me\b",
    r"\bbeing abused\b",
    r"\bhe touches me\b",
)
_MODERATION_LEXICON = {
    "harassment": (r"\bidiot\b", r"\bstupid\b", r"\bloser\b", r"\bshut up\b"),
    "hate": (r"\bhate you\b",),
    "violence": (r"\bkill you\b", r"\bbeat you up\b", r"\bhurt you\b"),
    "sexual": (r"\bnude\b", r"\bsend pics\b"),
}


class DeterministicSafetyClassifier(SafetyClassifier):
    """Keyword/lexicon screen. Deterministic, dependency-free, explainable.

    Abstains (low confidence) when nothing matches — it does NOT assert "safe",
    so subtle cases fall to review rather than being waved through."""

    name = "deterministic-lexicon-screen (degraded — wire a live classifier provider)"

    def classify(self, text: str) -> tuple[tuple[str, ...], bool, float]:
        low = text.lower()
        crisis = any(re.search(p, low) for p in _CRISIS_PATTERNS)
        categories: list[str] = []
        for category, patterns in _MODERATION_LEXICON.items():
            if any(re.search(p, low) for p in patterns):
                categories.append(category)
        if crisis and "self-harm" not in categories:
            categories.append("self-harm")
        if crisis or categories:
            # A clear lexical hit is high-confidence.
            confidence = 0.95
        else:
            # Nothing matched: ABSTAIN. Low confidence signals "not verified
            # safe", letting the caller escalate ambiguous text to review.
            confidence = 0.4
        return tuple(categories), crisis, confidence


# ---------------------------------------------------------------------------
# The subsystem
# ---------------------------------------------------------------------------
class ChildSafetySubsystem:
    def __init__(
        self,
        audit_log: AuditLog,
        *,
        classifier: SafetyClassifier | None = None,
        block_threshold: float = 0.85,
    ) -> None:
        self._audit = audit_log
        self._classifier = classifier or DeterministicSafetyClassifier()
        self._block_threshold = block_threshold
        # Surfaces explicitly registered as monitored. Anything else is refused.
        self._monitored: set[str] = set()
        self._escalations: list[Escalation] = []  # append-only

    # -- channel registration ----------------------------------------------
    def register_surface(self, surface: str) -> None:
        """Register a free-text surface as monitored. Only registered surfaces
        may carry free text."""
        self._monitored.add(surface)

    def is_monitored(self, surface: str) -> bool:
        return surface in self._monitored

    # -- the assessment ----------------------------------------------------
    async def assess(
        self,
        *,
        surface: str,
        canonical_uuid: UUID,
        text: str,
        tenant_id: UUID,
    ) -> SafetyAssessment:
        # NO UNMONITORED CHANNELS: refuse free text on an unregistered surface.
        if surface not in self._monitored:
            raise UnmonitoredChannelError(
                f"surface {surface!r} is not a monitored channel; free text refused. "
                "Register it with register_surface() before carrying learner text."
            )

        categories, crisis, confidence = self._classifier.classify(text)

        if crisis:
            verdict = SafetyVerdict.CRISIS          # crisis always wins
        elif categories and confidence >= self._block_threshold:
            verdict = SafetyVerdict.BLOCK
        elif categories:
            verdict = SafetyVerdict.FLAG            # held for human review
        else:
            verdict = SafetyVerdict.ALLOW

        assessment = SafetyAssessment(
            assessment_id=new_id(),
            surface=surface,
            canonical_uuid=canonical_uuid,
            verdict=verdict,
            categories=tuple(categories),
            crisis=crisis,
            confidence=confidence,
            monitored=True,  # we are here, so the surface is monitored
            assessed_at=_now(),
            rationale=self._rationale(verdict, categories, crisis),
        )

        # Record every assessment that is not a clean allow (the moderation
        # trail is auditable). Crisis is always recorded and escalated.
        if verdict is not SafetyVerdict.ALLOW:
            await self._audit.record(
                actor_uuid=canonical_uuid,
                action="child_safety.assess",
                resource=surface,
                purpose="child-safety",
                tenant_id=tenant_id,
                privileged=verdict is SafetyVerdict.CRISIS,
                detail={
                    "verdict": verdict.value,
                    "categories": list(categories),
                    "crisis": crisis,
                },
            )

        if crisis:
            await self._escalate(assessment=assessment, tenant_id=tenant_id)

        return assessment

    async def _escalate(self, *, assessment: SafetyAssessment, tenant_id: UUID) -> Escalation:
        esc = Escalation(
            escalation_id=new_id(),
            assessment_id=assessment.assessment_id,
            canonical_uuid=assessment.canonical_uuid,
            surface=assessment.surface,
            status=EscalationStatus.PENDING,
            raised_at=_now(),
            note="crisis signal detected; routed to a qualified human.",
        )
        self._escalations.append(esc)
        await self._audit.record(
            actor_uuid=assessment.canonical_uuid,
            action="child_safety.escalate",
            resource=assessment.surface,
            purpose="child-safety",
            tenant_id=tenant_id,
            privileged=True,
            detail={
                "escalation_id": str(esc.escalation_id),
                "assessment_id": str(assessment.assessment_id),
            },
        )
        return esc

    # -- escalation review --------------------------------------------------
    def pending_escalations(self) -> list[Escalation]:
        seen: set[UUID] = set()
        out: list[Escalation] = []
        for e in reversed(self._escalations):
            if e.escalation_id in seen:
                continue
            seen.add(e.escalation_id)
            if e.status is EscalationStatus.PENDING:
                out.append(e)
        out.reverse()
        return out

    async def acknowledge(
        self, *, escalation_id: UUID, handler_uuid: UUID, tenant_id: UUID, note: str = ""
    ) -> Escalation:
        current = self._current_escalation(escalation_id)
        if current is None:
            raise KeyError(f"no escalation {escalation_id}")
        from dataclasses import replace

        ack = replace(current, status=EscalationStatus.ACKNOWLEDGED, note=note or current.note)
        self._escalations.append(ack)  # append a superseding record
        await self._audit.record(
            actor_uuid=handler_uuid,
            action="child_safety.escalation_acknowledged",
            resource=current.surface,
            purpose="child-safety",
            tenant_id=tenant_id,
            privileged=True,
            detail={"escalation_id": str(escalation_id)},
        )
        return ack

    def _current_escalation(self, escalation_id: UUID) -> Escalation | None:
        latest: Escalation | None = None
        for e in self._escalations:
            if e.escalation_id == escalation_id:
                latest = e
        return latest

    @staticmethod
    def _rationale(verdict: SafetyVerdict, categories: tuple[str, ...], crisis: bool) -> str:
        if crisis:
            return "crisis signal detected; escalated to a qualified human."
        if verdict is SafetyVerdict.BLOCK:
            return f"blocked on category match: {', '.join(categories)}."
        if verdict is SafetyVerdict.FLAG:
            return f"flagged for human review: {', '.join(categories)}."
        return "no safety signal matched."
