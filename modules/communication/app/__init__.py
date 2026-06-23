"""Relationships & communication module (B9).

A capability module over the secure core. It owns the companion / care surface,
parent engagement + parent–teacher partnership, the communication hub, and
safeguarding (the child-safety subsystem on every free-text surface), with a
multilingual + code-switching translation interface. The package surface:

  - ``companion``          — the role-shaped, BOUNDED companion. No manipulation /
                             exclusivity / dependence; serious matters ESCALATE to
                             qualified humans. Screens every message first; never
                             counsels a crisis.
  - ``hub``                — the communication hub. Free-text messages are always
                             screened, and a message can become a routed, owned,
                             tracked TASK; cross-context routing is consent-gated.
  - ``parent_partnership`` — parent engagement framed as partnership + pride,
                             never surveillance. Every cross-context read is
                             consent-gated (fail-closed) and surveillance purposes
                             are refused outright.
  - ``safeguarding``       — the CHILD-SAFETY subsystem: moderation, crisis
                             detection, escalation to qualified humans, and NO
                             unmonitored channels. Runs on every free-text
                             surface. Fail-safe deterministic fallback.
  - ``companion_memory``   — persistent, consent-gated, PII-free per-user
                             companion memory (thread + salient facts). Stateless
                             without consent; revocation purges.
  - ``delivery``           — multi-channel delivery adapters (chat / push / email
                             / SMS / a WhatsApp-class channel) over one trigger
                             layer. Only SCREENED messages route; real sends need
                             approval; degrades to an in-memory outbox.
  - ``parent_feedback``    — parent-specific celebration/growth/next-step feedback
                             generated FROM real signals via generate-and-verify
                             (grounded + confidence-gated; never canned).
  - ``meeting_assistant``  — the in-meeting SILENT, CONSENTED assistant:
                             transcription, notes, key-point extraction, and
                             prepared (never auto-fired) action items.
  - ``today``              — the "what do I need to do today" synthesis from role
                             + timetable + tasks + permissions + progress;
                             permission-aware, approval-aware, explainable.
  - ``translation``        — the multilingual + code-switching interface that
                             preserves subject terminology. Degrades to a
                             pass-through that never drops content.
  - ``events``             — emit message / meeting / sentiment / safeguarding
                             events on the contract envelope (opaque ids only,
                             never the message body; append-only).
  - ``config``             — env-var NAMES only (degrades gracefully with none).

Import-safe: importing the package, or any submodule, performs no I/O, reads no
secret value, and never requires a live provider. The deterministic paths are
the supported paths until the gateway, orchestrator, safety service, consent
authority, and translation provider are wired.
"""

from __future__ import annotations

from . import (  # noqa: F401
    companion,
    companion_memory,
    config,
    delivery,
    events,
    hub,
    meeting_assistant,
    parent_feedback,
    parent_partnership,
    safeguarding,
    today,
    translation,
)

__all__ = [
    "companion",
    "companion_memory",
    "config",
    "delivery",
    "events",
    "hub",
    "meeting_assistant",
    "parent_feedback",
    "parent_partnership",
    "safeguarding",
    "today",
    "translation",
]

__version__ = "0.1.0"
