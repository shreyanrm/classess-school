"""Pytest bootstrap for the institution module.

Adds the module root to ``sys.path`` so ``import app...`` resolves when tests run
from the module directory. Touches nothing else — the app modules are pure and
discover no spine by path (import-safe, no I/O at import).
"""

from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
