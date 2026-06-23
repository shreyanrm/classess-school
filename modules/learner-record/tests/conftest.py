"""Pytest bootstrap + shared fixtures for the learner-record module (B8).

Adds the module root to ``sys.path`` so ``import app...`` resolves when tests
run from the module directory. Import-safe and offline: no network, no provider,
no build step, no secret value read. The deterministic (degraded) paths are the
ones exercised — they are the supported paths until a provider is wired.

All identifiers below are OPAQUE placeholders standing in for canonical_uuids /
ontology ids — never PII, never a real name (CONFIDENTIALITY discipline).
"""

from __future__ import annotations

import os
import sys
import uuid

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _id() -> str:
    return str(uuid.uuid4())


# Opaque actors and consent — generic labels only.
LEARNER_A = _id()        # the learner whose record this is
TEACHER = _id()          # a School viewer in the consented audience
PARENT = _id()           # the Parent surface viewer (partnership, gated)
OUTSIDER = _id()         # a viewer with no consent — must be denied
CONSENT = _id()

# Opaque ontology + evidence ids.
T_FRACTIONS = _id()
T_GEOMETRY = _id()
EVENT_1 = _id()
EVENT_2 = _id()
