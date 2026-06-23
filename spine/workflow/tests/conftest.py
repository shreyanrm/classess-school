"""Make the ``app`` package importable when tests run from this directory.

Adds the workflow package root (the parent of ``app``) to sys.path so
``from app import ...`` resolves without an install step.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parents[1]
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))
