"""Pytest bootstrap for the coursework module.

Adds the module root to ``sys.path`` so ``import app...`` resolves when tests run
from the module directory. Does NOT touch the spine — the app modules discover
the ai-fabric verify substrate by file path on their own (import-safe).
"""

from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
