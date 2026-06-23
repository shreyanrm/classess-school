"""Pytest config: make the module package importable without installation.

Runs with no network and no DB. Adds the module root to ``sys.path`` so
``import app`` works from a checkout.
"""

from __future__ import annotations

import os
import sys

_MODULE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _MODULE_ROOT not in sys.path:
    sys.path.insert(0, _MODULE_ROOT)
