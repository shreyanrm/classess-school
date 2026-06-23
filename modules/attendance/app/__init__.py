"""Attendance intelligence (d8).

Multi-method attendance capture, risk detection, cross-method
reconciliation and staff attendance for the Classess platform.

Design invariants honoured by this package:

- Behavioural data carries ONLY an opaque ``canonical_uuid``. No PII
  (names, phone numbers, photos) is stored or emitted anywhere in this
  package. Capture inputs are reduced to opaque references before any
  record is produced.
- Capture ASSISTS, never auto-finalises. Every capture method produces a
  *draft* roll that a human (the teacher) must confirm. Confirmation is an
  explicit, separate, consequential step on the permission ladder.
- Events are immutable and append-only. The :mod:`app.events` builders
  return frozen payloads; nothing in this package mutates a previously
  emitted event.
- Offline-capable shape. Capture, reconciliation and risk detection are
  pure functions over in-memory data with no network or DB dependency, so
  a device can capture offline and sync the resulting draft/event later.
- Generate-and-verify + confidence gate. Assisted methods attach a
  confidence to every suggestion; low-confidence suggestions are surfaced
  for review rather than silently accepted.

Secrets are ENV-ONLY (see README). This package never hardcodes a secret.
"""

from __future__ import annotations

__all__ = [
    "capture",
    "risk",
    "reconciliation",
    "staff",
    "events",
]

__version__ = "0.1.0"
