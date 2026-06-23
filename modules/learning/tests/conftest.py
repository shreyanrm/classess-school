"""Test fixtures for the Learning module.

Import-safe and offline: no network, no provider, no build step. The package is
made importable without installation (no install is ever run). Deterministic
clock and opaque ids so every assertion is reproducible.

The whole suite runs without pydantic and without the spine engine installed —
it exercises the module's deterministic (degraded) paths, which are the
supported paths until a provider is wired. Tests that need the CORE engine skip
cleanly when it is unavailable.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# Make the `learning` package importable without installation. tests -> learning
# -> modules; put `modules` on the path so `import learning` resolves.
_MODULES_ROOT = Path(__file__).resolve().parents[2]
if str(_MODULES_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULES_ROOT))

# Deterministic clock (mirrors the spine test fixtures).
NOW = datetime(2026, 6, 22, 12, 0, 0, tzinfo=timezone.utc)

# Opaque ids — random-shaped tokens, never PII (INVARIANT 1, 2).
LEARNER_A = "aaaaaaaa-0000-4000-8000-000000000001"
CONSENT = "cccccccc-0000-4000-8000-000000000003"
T_EUCLID = "70910000-0000-4000-8000-000000000301"
T_TRIG = "70910000-0000-4000-8000-000000000306"


def days_ago(n: int) -> datetime:
    return NOW - timedelta(days=n)


@pytest.fixture
def now() -> datetime:
    return NOW
