"""Scheduling & continuity module (B2).

A capability module over the secure core. It owns the academic calendar, the
dynamic timetable + constraint solver, the substitution ladder, pacing
protection, and teacher knowledge transfer. The package surface:

  - ``calendar``     — terms, holidays, and working-day math (board-agnostic).
  - ``timetable``    — the dynamic timetable + the constraint solver. Classifies
                       rules hard/soft/contextual and produces SCORED
                       ALTERNATIVES for human approval. Never auto-commits.
  - ``substitution`` — the substitution ladder Level 1-6 (never a free period);
                       produces ranked, human-approvable substitute options.
  - ``pacing``       — planned-vs-delivered tracking, drift detection, and the
                       teacher knowledge-transfer (handover) note.
  - ``events``       — emit timetable/attendance-trigger/pacing events on the
                       contract envelope (opaque ids only; append-only).
  - ``config``       — env-var NAMES only (degrades gracefully with none set).

Import-safe: importing the package, or any submodule, performs no I/O, reads no
secret value, and never requires a live provider. The deterministic paths are
the supported paths until the gateway, event store, and workflow engine are
wired.
"""

from __future__ import annotations

from . import (  # noqa: F401
    calendar,
    config,
    events,
    pacing,
    substitution,
    timetable,
)

__all__ = [
    "calendar",
    "config",
    "events",
    "pacing",
    "substitution",
    "timetable",
]

__version__ = "0.1.0"
