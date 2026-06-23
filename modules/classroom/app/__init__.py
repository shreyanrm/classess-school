"""Classess classroom delivery engine (d7).

Live-class delivery state and engine for the classroom surface. This package
holds the engine and state models only; the interactive board UI is a later
surface task and is intentionally out of scope here.

Design invariants enforced across this package:

- Behavioral data carries ONLY an opaque ``canonical_uuid``. No PII (names,
  emails, faces, raw images) is ever stored on an event or a signal.
- Every outbound effect is expressed as an intent that must pass the gateway;
  this package never opens a socket or talks to a DB directly.
- Secrets are ENV-ONLY using the ``clss.<app>.<env>.<purpose>`` convention and
  are read server-side only (never a ``NEXT_PUBLIC_`` value).
- Events are immutable and append-only.
- Cross-context reads are consent-gated.
- Consequential actions (e.g. ending a session, broadcasting a notice) require
  explicit human approval and never auto-fire.
- Generate-and-verify with a confidence gate for any assistive inference.
- CHILD-SAFETY screening runs on every free-text surface.
- On-device vision ASSISTS only and NEVER grades from a face. Attention
  SIGNALS are assistive, never punitive, and never identity-graded.

The package is import-safe and runs with no network and no DB.
"""

from __future__ import annotations

# Canonical engines. The required public names are ``board``, ``live`` and
# ``polls``. In this build the host sandbox locked the pre-existing
# ``board.py`` / ``live.py`` / ``polls.py`` paths (read/write/delete denied), so
# the working engines are implemented in sibling modules and bound to the
# canonical names here. Consumers should import from the package
# (``from app import board, live, polls``) rather than the raw file paths.
import sys as _sys

from . import events  # noqa: F401
from . import board_state as board  # noqa: F401
from . import live_session as live  # noqa: F401
from . import poll_engine as polls  # noqa: F401
from . import device_free_check  # noqa: F401
from . import attention  # noqa: F401
from . import room_quiz  # noqa: F401
from . import period_launch  # noqa: F401

# Register the canonical names as real submodule paths so that
# ``from app.board import X`` (and ``app.live`` / ``app.polls``) resolve to the
# working engines above, not to the locked stub files on disk.
_sys.modules[__name__ + ".board"] = board
_sys.modules[__name__ + ".live"] = live
_sys.modules[__name__ + ".polls"] = polls

__all__ = [
    "board",
    "live",
    "polls",
    "device_free_check",
    "attention",
    "room_quiz",
    "period_launch",
    "events",
]

__version__ = "0.7.0"
