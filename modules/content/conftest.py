"""Make ``modules/content`` importable as the ``content`` package under pytest.

Adds the ``modules`` directory to ``sys.path`` so ``import content`` resolves
when pytest is run from this directory or the repo root. The content package's
own ``_spine`` shim puts the ai-fabric spine on the path. Import-safe, no
network, no secrets.
"""

import os
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_MODULES_DIR = os.path.abspath(os.path.join(_THIS, ".."))

for path in (_MODULES_DIR,):
    if path not in sys.path:
        sys.path.insert(0, path)
