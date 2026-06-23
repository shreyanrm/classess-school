"""Child-safety + PII guards for attendance free-text surfaces.

Every free-text surface in this module (capture notes, reconciliation
review notes, risk annotations) must pass through :func:`screen_free_text`
before it is accepted. The screen is conservative and offline: it never
calls a network service, so it degrades gracefully with no live keys.

The screen does two things:

1. PII guard - rejects content that looks like it carries personally
   identifying information (phone numbers, emails, long digit runs that
   could be IDs). Behavioural data must carry only the opaque
   ``canonical_uuid``.
2. Child-safety guard - flags content matching a conservative block list
   of self-harm / abuse / contact-grooming markers so it can be routed to
   a human review queue instead of being stored verbatim.

This is a defence-in-depth local filter. The authoritative child-safety
classifier lives behind the gateway; this guard exists so that an offline
device never persists unscreened free text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

# --- PII detectors ---------------------------------------------------------

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Phone-like: 10+ digits, optionally grouped with spaces/dashes/parens/+.
_PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{8,}\d)")
# Bare long digit run that is likely an external identifier (not a UUID).
_LONG_DIGITS_RE = re.compile(r"\b\d{7,}\b")

# --- Child-safety markers (conservative, lowercase substring match) --------
# Kept deliberately small and generic. The gateway classifier is the
# authoritative source; these only force local content into review.
_SAFETY_MARKERS = (
    "kill myself",
    "kill my self",
    "want to die",
    "end my life",
    "hurt myself",
    "self harm",
    "self-harm",
    "suicide",
    "abuse",
    "hit me",
    "beat me",
    "touch me",
    "don't tell anyone",
    "dont tell anyone",
    "our secret",
    "meet me alone",
)

MAX_FREE_TEXT_LEN = 500


@dataclass(frozen=True)
class ScreenResult:
    """Outcome of screening a free-text surface."""

    ok: bool
    # Sanitised text safe to persist (PII redacted). Empty when not ok.
    sanitized: str = ""
    # Reasons the text was rejected or flagged.
    pii_findings: List[str] = field(default_factory=list)
    safety_findings: List[str] = field(default_factory=list)
    # True when a child-safety marker fired -> route to human review.
    needs_human_review: bool = False


def _redact_pii(text: str) -> "tuple[str, List[str]]":
    findings: List[str] = []
    out = text
    if _EMAIL_RE.search(out):
        findings.append("email")
        out = _EMAIL_RE.sub("[redacted-contact]", out)
    if _PHONE_RE.search(out):
        findings.append("phone")
        out = _PHONE_RE.sub("[redacted-contact]", out)
    if _LONG_DIGITS_RE.search(out):
        findings.append("long_digit_run")
        out = _LONG_DIGITS_RE.sub("[redacted-id]", out)
    return out, findings


def screen_free_text(text: str | None) -> ScreenResult:
    """Screen a free-text surface for PII and child-safety markers.

    Returns a :class:`ScreenResult`. Callers MUST NOT persist the original
    text; persist :attr:`ScreenResult.sanitized` only, and only when
    :attr:`ScreenResult.ok` is true. If ``needs_human_review`` is set, the
    content must be routed to the human review queue.
    """

    if text is None:
        return ScreenResult(ok=True, sanitized="")

    if len(text) > MAX_FREE_TEXT_LEN:
        return ScreenResult(
            ok=False,
            pii_findings=["too_long"],
        )

    sanitized, pii = _redact_pii(text)

    lowered = text.lower()
    safety = [m for m in _SAFETY_MARKERS if m in lowered]

    needs_review = bool(safety)
    # Content carrying PII is not OK to persist as-is; we redact, so the
    # sanitised form is OK to keep, but we still report the finding.
    ok = not needs_review

    return ScreenResult(
        ok=ok,
        sanitized=sanitized,
        pii_findings=pii,
        safety_findings=safety,
        needs_human_review=needs_review,
    )


def assert_no_pii_identifier(value: str) -> None:
    """Guard that an identifier slot carries an opaque uuid, not PII.

    Raises ``ValueError`` if ``value`` looks like an email or phone number.
    Used by event/record builders to refuse PII in identifier fields.
    """

    if _EMAIL_RE.search(value) or _PHONE_RE.search(value):
        raise ValueError(
            "identifier field must be an opaque canonical_uuid, not PII"
        )
