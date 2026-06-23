"""Classess AI fabric (spine A4).

The model router + generate-and-verify substrate. Exposes generation,
evaluation, and conversation behind structured-output validation and a
CONFIDENCE GATE. Track 1 (external LLM routing) and Track 2 (proprietary /
edge models) are kept configurationally SEPARATE (INVARIANT 11).

Nothing generated is served unverified (INVARIANT 7). Agents hold no
credentials and invoke only governed, least-privilege capabilities
(INVARIANT 8 — the permission ladder).
"""

from __future__ import annotations

__all__ = [
    "router",
    "verify",
    "capability_registry",
    "orchestrator",
    "observability",
    "config",
    "voice",
    "track2",
]

__version__ = "0.1.0"
