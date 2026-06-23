"""Governance & safety (spine A7).

The most powerful surfaces are the best governed. This package owns:

- ``audit``        — the immutable audit query layer over append-only logs.
- ``breakglass``   — privileged access requires a reason, is recorded
                     immutably, and is reviewable.
- ``control_centre`` — the AI control centre: model usage, Track 1 / Track 2
                     view, confidence-gate stats, emergency disable.
- ``consent``      — consent + retention + lineage services (lineage on every
                     insight).
- ``child_safety`` — moderation, crisis detection, escalation to qualified
                     humans, no unmonitored channels — runs on every free-text
                     surface.
- ``tenancy``      — tenant isolation policy across group / franchise /
                     programme / network.

Deterministic-first and dependency-free: every module runs on the standard
library alone, is import-safe, and the test suite passes with no network and no
database. Live backends (Postgres audit sink, classifier provider) wire in
later behind named env vars with no re-architecture.
"""

from __future__ import annotations

__all__ = [
    "audit",
    "breakglass",
    "control_centre",
    "consent",
    "child_safety",
    "tenancy",
    "config",
    "models",
]
