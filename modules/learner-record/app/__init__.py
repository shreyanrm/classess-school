"""Classess School — Learner-record module (B8).

The School-facing COMPOSITION of the evidence graph: the evidence-linked
profile, the portfolio, and verifiable credentials. B8 READS governed, consent +
purpose-gated views of the learner graph and evidence store — never bulk reads,
never PII — and composes them into a record the School can show.

What B8 owns:
  - ``access``      : the consent + purpose gate on every read (denied-by-default).
  - ``profile``     : the evidence-linked profile — independent vs support-dependent
                      mastery in PLAIN LANGUAGE, never a number; every item carries
                      its source + permission controls.
  - ``portfolio``   : curated artifacts with provenance.
  - ``credentials`` : verifiable, portable credentials under the learner's control.
  - ``events``      : portfolio / credential events (append-only, gateway-degrading).

What B8 does NOT do: it never authors mastery, never computes a score, never
reads without a satisfied consent + purpose check, and never carries PII. The
mastery judgment is a spine concern (A3) read through governed views.

Import-safe: importing this package performs no I/O, opens no connection, and
reads no secret value. Submodules import their (optional) dependencies lazily.
"""

from __future__ import annotations

from .config import LearnerRecordSettings, get_settings

__all__ = [
    "LearnerRecordSettings",
    "get_settings",
    # Submodules — imported by name for discoverability.
    "access",
    "profile",
    "portfolio",
    "credentials",
    "events",
]

__version__ = "0.1.0"
