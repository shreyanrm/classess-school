"""Pytest bootstrap so ``import app...`` resolves from the package root.

Keeps the suite import-safe and runnable from anywhere with no install step, no
network and no DB.
"""

import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
