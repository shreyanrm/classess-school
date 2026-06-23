"""Pytest path setup so the `planning` package imports without installation.

Import-safe: no network, no DB. Adds the `modules/` directory (the parent of the
`planning` package) to sys.path.
"""

import os
import sys

# tests/ -> planning/ -> modules/
_MODULES_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if _MODULES_DIR not in sys.path:
    sys.path.insert(0, _MODULES_DIR)
