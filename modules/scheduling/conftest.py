"""Pytest bootstrap for the scheduling module.

Adds the module root to ``sys.path`` so ``import app...`` resolves when tests run
from the module directory. Import-safe and offline: no network, no provider, no
build step, no secret value read. The deterministic (degraded) paths are the
ones exercised — they are the supported paths until a provider is wired.
"""

from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
