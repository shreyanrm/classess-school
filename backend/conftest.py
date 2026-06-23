"""Pytest bootstrap for the backend deployable tests.

The deployable composes the spine + capability modules in-process via
``backend.loader`` (which aliases each ``app`` package). For ``import backend...``
to resolve when pytest runs from this directory, the REPO ROOT (the parent of
this ``backend`` dir) must be on ``sys.path``. We add it here instead of doing a
``pip install`` — nothing is installed to run the tests.
"""

from __future__ import annotations

import os
import sys

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_BACKEND_DIR)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
