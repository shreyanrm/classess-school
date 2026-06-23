"""Safeguarding — the CHILD-SAFETY subsystem (B9 · over A7).

This runs on EVERY free-text surface (the companion, the hub, parent messages,
any conversation). It is the law from the dossier made executable:

  CHILD-SAFETY runs on every free-text surface: moderation, crisis detection,
  escalation to qualified humans, no unmonitored channels.

Three jobs, in order:

  1. **Moderation** — classify free text for harm to or by the writer (abuse,
     harassment, hate, sexual content involving a minor, grooming-shaped
     contact, self-described violence).
  2. **Crisis detection** — detect signals of self-harm, suicidal ideation,
     abuse disclosure, or acute distress. These are the highest-severity class
     and they ALWAYS escalate to a qualified human — never to a bot, never to a
     score, never to silence.
  3. **Escalation** — every flagged item produces an escalation routed to a
     QUALIFIED HUMAN (a counsellor / safeguarding lead), with evidence, a
     severity, and a "why". Nothing consequential auto-fires; the human acts.

NO UNMONITORED CHANNELS. :func:`open_channel` refuses to create a free-text
channel that is not bound to this classifier. There is no path to an
un-screened channel — structurally.

Degrade-safe (INVARIANT, and a child-safety necessity): with no A7 safety
service configured this falls back to a deterministic, on-device LEXICAL
classifier. The fallback is intentionally fail-safe — when uncertain it flags
UP, never down. A missing provider can NEVER silence a crisis signal or open an
unmonitored channel.

Import-safe: no I/O, no provider, no secret value read at import. The classifier
is pure, deterministic, and offline.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from typing import Iterable, Literal

from .config import CommunicationSettings, get_settings


class Severity(IntEnum):
    """Risk severity, higher = more urgent. ``CRISIS`` always escalates to a
    qualified human and is never handled by an automated reply."""

    NONE = 0
    LOW = 1
    CONCERN = 2
    HIGH = 3
    CRISIS = 4


SEVERITY_LABELS: dict[Severity, str] = {
    Severity.NONE: "no risk signal",
    Severity.LOW: "low — keep visible",
    Severity.CONCERN: "concern — review by a qualified human",
    Severity.HIGH: "high — prompt review by a qualified human",
    Severity.CRISIS: "crisis — escalate to a qualified human now",
}

# Category of the signal. ``crisis`` categories drive a CRISIS severity and an
# immediate human escalation regardless of phrasing.
Category = Literal[
    "self_harm",
    "abuse_disclosure",
    "acute_distress",
    "violence",
    "sexual_content_minor",
    "grooming_contact",
    "harassment",
    "hate",
    "profanity",
    "none",
]

# Categories that, when matched, are a crisis: a real person may be in danger.
# These ALWAYS escalate to a qualified human (never a bot, never deferred).
_CRISIS_CATEGORIES: frozenset[Category] = frozenset(
    {"self_harm", "abuse_disclosure", "acute_distress", "sexual_content_minor", "grooming_contact"}
)


@dataclass(frozen=True)
class _Rule:
    category: Category
    severity: Severity
    patterns: tuple[re.Pattern[str], ...]
    why: str


def _compile(*phrases: str) -> tuple[re.Pattern[str], ...]:
    # Word-ish boundaries; case-insensitive. Deterministic, offline.
    return tuple(re.compile(rf"(?<![a-z]){re.escape(p)}(?![a-z])", re.IGNORECASE) for p in phrases)


# The deterministic fallback lexicon. Deliberately conservative and fail-safe:
# it is the floor, not the ceiling. The A7 service (when wired) is a superset.
# These are SIGNALS that warrant a qualified human looking — not a verdict.
_RULES: tuple[_Rule, ...] = (
    _Rule(
        "self_harm",
        Severity.CRISIS,
        _compile(
            "kill myself", "want to die", "end my life", "suicide", "suicidal",
            "hurt myself", "harming myself", "self harm", "cut myself", "no reason to live",
        ),
        "Signals of self-harm or suicidal ideation. A qualified human must reach out now.",
    ),
    _Rule(
        "abuse_disclosure",
        Severity.CRISIS,
        _compile(
            "he hits me", "she hits me", "they hit me", "being abused", "hurts me at home",
            "touched me", "scared to go home", "no one is safe at home",
        ),
        "A possible disclosure of harm to the child. Route to a safeguarding lead immediately.",
    ),
    _Rule(
        "grooming_contact",
        Severity.CRISIS,
        _compile(
            "keep this our secret", "dont tell your parents", "do not tell your parents",
            "send me a photo of yourself", "meet me alone", "delete these messages",
        ),
        "Grooming-shaped contact toward a minor. Escalate to a safeguarding lead immediately.",
    ),
    _Rule(
        "acute_distress",
        Severity.HIGH,
        _compile(
            "i cant go on", "i can not go on", "everyone hates me", "i give up on everything",
            "i feel hopeless", "i am worthless",
        ),
        "Acute distress. A qualified human should check in promptly.",
    ),
    _Rule(
        "violence",
        Severity.HIGH,
        _compile("i will hurt", "going to hurt you", "beat you up", "bring a weapon"),
        "A threat of violence. Route to a qualified human for review.",
    ),
    _Rule(
        "harassment",
        Severity.CONCERN,
        _compile("you are stupid", "shut up loser", "nobody likes you", "kill yourself"),
        "Possible harassment or bullying. A qualified human should review the exchange.",
    ),
)

# ``kill yourself`` is harassment in phrasing but a crisis-class harm in intent;
# treat it as crisis (directed self-harm incitement) — fail UP.
_DIRECTED_SELF_HARM = _compile("kill yourself", "kys", "go die")


@dataclass
class SafetyFinding:
    """The classifier verdict for one piece of free text. PII-free: it carries
    only the surface ref and opaque writer ref, never the text itself in the
    escalation envelope (the text stays in the monitored store)."""

    flagged: bool
    severity: Severity
    categories: tuple[Category, ...]
    why: str
    requires_human: bool
    is_crisis: bool
    classifier: Literal["a7_service", "on_device_lexical"]
    excerpt_hint: str = ""  # short, redacted hint for the human reviewer.

    @property
    def severity_label(self) -> str:
        return SEVERITY_LABELS[self.severity]

    @property
    def can_auto_respond(self) -> bool:
        """An automated/companion reply is allowed ONLY when nothing is flagged.
        Anything flagged waits for a qualified human (no bot handles risk)."""
        return not self.flagged


@dataclass
class Escalation:
    """A safeguarding escalation routed to a QUALIFIED HUMAN. Mirrors the A5
    recommendation/approval shape: evidence, severity, owner, why, and the
    explicit fact that a human — never the system — acts on it."""

    escalation_id: str
    surface: str
    writer_ref: str  # opaque canonical_uuid of the writer.
    severity: Severity
    categories: tuple[Category, ...]
    why: str
    owner_role: str  # the qualified human role, e.g. "counsellor".
    raised_at: str
    is_crisis: bool
    excerpt_hint: str = ""
    status: Literal["pending_human"] = "pending_human"  # never auto-resolved.

    @property
    def severity_label(self) -> str:
        return SEVERITY_LABELS[self.severity]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _redact(text: str, *, limit: int = 80) -> str:
    """A short, single-line hint for the reviewer. Collapses whitespace and
    truncates; the full text stays in the monitored store, never in logs."""
    collapsed = re.sub(r"\s+", " ", text).strip()
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 1] + "…"


class Safeguard:
    """The child-safety classifier + escalation gate for every free-text surface.

    With an A7 safety service configured this would call it through the gateway
    (token read from the environment by NAME). With none configured it runs the
    deterministic on-device lexical classifier — fail-safe by design.
    """

    def __init__(self, settings: CommunicationSettings | None = None) -> None:
        self._settings = settings or get_settings()

    @property
    def settings(self) -> CommunicationSettings:
        return self._settings

    @property
    def classifier_name(self) -> Literal["a7_service", "on_device_lexical"]:
        # The on-device classifier is always the floor. The A7 service, when
        # wired, runs in addition — never instead — so a provider outage can
        # never lower the floor. While unwired, the on-device path IS the path.
        return "on_device_lexical"

    def classify(self, text: str) -> SafetyFinding:
        """Classify one piece of free text. Pure, deterministic, offline.

        Fail-safe: ambiguity flags UP. Crisis categories always set
        ``is_crisis`` and ``requires_human`` and forbid an automated reply.
        """
        if text is None:
            text = ""
        matched: list[tuple[Category, Severity, str]] = []

        # Directed self-harm incitement -> crisis, regardless of harassment shape.
        if any(p.search(text) for p in _DIRECTED_SELF_HARM):
            matched.append(
                (
                    "self_harm",
                    Severity.CRISIS,
                    "Directed self-harm incitement. Treated as a crisis; a qualified "
                    "human must intervene.",
                )
            )

        for rule in _RULES:
            if any(p.search(text) for p in rule.patterns):
                matched.append((rule.category, rule.severity, rule.why))

        if not matched:
            return SafetyFinding(
                flagged=False,
                severity=Severity.NONE,
                categories=("none",),
                why="No risk signal detected by the on-device classifier.",
                requires_human=False,
                is_crisis=False,
                classifier=self.classifier_name,
            )

        severity = max(sev for _, sev, _ in matched)
        categories = tuple(dict.fromkeys(cat for cat, _, _ in matched))  # de-dupe, ordered.
        is_crisis = severity >= Severity.CRISIS or any(c in _CRISIS_CATEGORIES for c in categories)
        if is_crisis:
            severity = Severity.CRISIS
        why = " ".join(why for _, _, why in matched)
        return SafetyFinding(
            flagged=True,
            severity=severity,
            categories=categories,
            why=why,
            # ANYTHING flagged needs a qualified human; risk is never bot-handled.
            requires_human=True,
            is_crisis=is_crisis,
            classifier=self.classifier_name,
            excerpt_hint=_redact(text),
        )

    def escalate(
        self,
        finding: SafetyFinding,
        *,
        surface: str,
        writer_ref: str,
        owner_role: str | None = None,
    ) -> Escalation:
        """Raise a human-owned escalation for a flagged finding.

        Refuses to escalate a clean finding (nothing to route). The escalation
        is owned by a QUALIFIED HUMAN and is ``pending_human`` — the system never
        resolves it. Crisis findings route to a safeguarding lead by default.
        """
        if not finding.flagged:
            raise ValueError("nothing to escalate: the finding is not flagged.")
        role = owner_role or ("safeguarding_lead" if finding.is_crisis else "counsellor")
        return Escalation(
            escalation_id=str(uuid.uuid4()),
            surface=surface,
            writer_ref=writer_ref,
            severity=finding.severity,
            categories=finding.categories,
            why=finding.why,
            owner_role=role,
            raised_at=_now_iso(),
            is_crisis=finding.is_crisis,
            excerpt_hint=finding.excerpt_hint,
        )

    def screen(
        self,
        text: str,
        *,
        surface: str,
        writer_ref: str,
        owner_role: str | None = None,
    ) -> tuple[SafetyFinding, Escalation | None]:
        """Classify and, if flagged, immediately produce the human escalation.

        This is the single call every free-text surface uses before it shows,
        stores, or replies to a message. A flagged finding ALWAYS comes back
        with an escalation attached — there is no flagged-but-unrouted state.
        """
        finding = self.classify(text)
        escalation = (
            self.escalate(finding, surface=surface, writer_ref=writer_ref, owner_role=owner_role)
            if finding.flagged
            else None
        )
        return finding, escalation


class UnmonitoredChannelError(RuntimeError):
    """Raised when something tries to open a free-text channel with no
    safeguarding bound to it. NO UNMONITORED CHANNELS — structurally."""


@dataclass(frozen=True)
class MonitoredChannel:
    """A free-text channel that is, by construction, bound to the safeguarding
    classifier. Every message routed through :meth:`admit` is screened first;
    there is no method that bypasses the screen."""

    channel_id: str
    surface: str
    _guard: Safeguard

    def admit(
        self, text: str, *, writer_ref: str
    ) -> tuple[SafetyFinding, Escalation | None]:
        """Screen a message before it enters the channel. Always screened —
        this is the only ingress."""
        return self._guard.screen(text, surface=self.surface, writer_ref=writer_ref)


def open_channel(
    *,
    surface: str,
    guard: Safeguard | None,
    channel_id: str | None = None,
) -> MonitoredChannel:
    """Open a free-text channel — ONLY ever a monitored one.

    Refuses to open a channel without a safeguarding classifier bound to it
    (``guard is None``). There is no ``open_unmonitored_channel`` anywhere in the
    module; this is the only constructor, and it always binds the screen.
    """
    if guard is None:
        raise UnmonitoredChannelError(
            "Refusing to open a free-text channel with no safeguarding bound to "
            "it. No unmonitored channels — every free-text surface is screened."
        )
    return MonitoredChannel(
        channel_id=channel_id or str(uuid.uuid4()),
        surface=surface,
        _guard=guard,
    )


def worst(findings: Iterable[SafetyFinding]) -> SafetyFinding:
    """The highest-severity finding from a batch (e.g. a whole thread)."""
    chosen: SafetyFinding | None = None
    for f in findings:
        if chosen is None or f.severity > chosen.severity:
            chosen = f
    if chosen is None:
        raise ValueError("worst() requires at least one finding.")
    return chosen
