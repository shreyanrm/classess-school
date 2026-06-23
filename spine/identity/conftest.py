"""Make the package importable as ``app`` when running pytest from this dir."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
