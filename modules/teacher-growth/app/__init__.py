"""Teacher growth module (B10).

Private, evidence-based teacher coaching over the secure core. It owns private
coaching signals, classroom-interaction analysis, the quality-review workflow,
and the continuity (knowledge-transfer) engine. The package surface:

  - ``interaction``    — deterministic classroom-interaction metrics from a
                         lesson's delivery/engagement events (talk ratio,
                         questioning quality, equity of voice, wait time).
  - ``coaching``       — PRIVATE, teacher-first coaching signals built from those
                         metrics. NO automated punitive ranking; employment
                         decisions require human review.
  - ``quality_review`` — the human-owned quality-review workflow (teacher
                         reflects first; a human reviewer signs off; nothing
                         auto-finalises).
  - ``continuity``     — the knowledge-transfer / handover note that travels with
                         a class on a change of hands (opaque refs only).
  - ``events``         — emit coaching-signal (PRIVATE), review-sign-off, and
                         handover events on the contract envelope (opaque ids
                         only; append-only).
  - ``config``         — env-var NAMES only (degrades gracefully with none set).

Two stances are enforced in code, not just documented: coaching signals are
private + teacher-first, and there is no code path that ranks teachers or lets a
machine make an employment decision.

Import-safe: importing the package, or any submodule, performs no I/O, reads no
secret value, and never requires a live provider. The deterministic paths are the
supported paths until the gateway, event store, and workflow engine are wired.
"""

from __future__ import annotations

from . import (  # noqa: F401
    coaching,
    config,
    continuity,
    events,
    interaction,
    quality_review,
)

__all__ = [
    "coaching",
    "config",
    "continuity",
    "events",
    "interaction",
    "quality_review",
]

__version__ = "0.1.0"
