# Attendance intelligence (d8)

Multi-method attendance capture, cross-method reconciliation, student and
staff risk detection, and the events that drive the rest of the platform -
including the trigger that asks scheduling to start its substitution
ladder.

This is a Python package. It is pure, offline-capable, and carries no PII.

## What it does

- **Capture (`app/capture.py`)** - five assisting methods, each of which
  builds a *draft* roll and never finalises it:
  - `photo-scan` - OCR of a paper register
  - `voice` - transcribed roll-call
  - `photo-roster` - classroom-photo presence hints
  - `absent-only` - teacher marks only absentees; the rest are *suggested*
    present
  - `online-presence` - join/heartbeat signals from a live session

  Every method returns a `DraftRoll`. A draft becomes attendance only via
  `confirm_roll(draft, confirmed_by=...)`, which **requires a human
  confirmer**. Capture assists; the teacher decides. Nothing auto-finalises.

- **Reconciliation (`app/reconciliation.py`)** - combines drafts from
  several methods for the same session. Where methods agree it proposes a
  single status; where they materially disagree (present vs absent) it
  **flags a conflict for human review** instead of silently picking a
  winner.

- **Risk (`app/risk.py`)** - detects three kinds of attendance risk:
  - `consecutive` - an unbroken run of absences
  - `chronic` - a high absence rate over a rolling window
  - `pattern` - structured absence (for example the same weekday)

  Findings are advisory and carry `needs_human_review`.

- **Staff (`app/staff.py`)** - daily staff attendance. A confirmed staff
  absence with assigned sessions produces a substitution request event.

- **Events (`app/events.py`)** - immutable, append-only event payloads for
  roll confirmation, individual marks, risk flags, reconciliation conflicts
  and staff records. `substitution_needed_event(...)` is the trigger that
  asks the **scheduling** module to start its (human-gated) substitution
  ladder - it requests cover, it never schedules a substitute itself.

## Invariants honoured

- **PII-free** - behavioural data carries only the opaque `canonical_uuid`.
  Identifier slots are guarded (`app/safety.assert_no_pii_identifier`).
- **Capture assists, humans confirm** - the draft -> confirm step is the
  only path to finalised attendance and always needs a human confirmer.
  Consequential actions (substitution) are built only from confirmed state.
- **Immutable, append-only events** - event builders return frozen objects;
  there is no update path. `collect_append_only` never mutates its input.
- **Consent / gateway** - events are produced here and transported by the
  gateway (`to_envelope`); this package performs no cross-context read.
- **Generate-and-verify + confidence gate** - assisted marks carry a
  confidence; low-confidence and unknown marks are routed to review.
- **Child-safety on every free-text surface** - all notes pass through
  `app/safety.screen_free_text`, which redacts PII and routes content with
  child-safety markers to human review. The local screen is conservative
  and offline; the authoritative classifier lives behind the gateway.
- **Degrades gracefully offline** - no network or DB is required; capture
  and event building work on a disconnected device and sync later.

## Environment variables (names only - values are ENV-ONLY, never hardcoded)

Secrets follow the `clss.<app>.<env>.<purpose>` naming convention and are
server-side only (never `NEXT_PUBLIC_*`). This package itself reads no
secrets; the names below are consumed by the gateway/transport layer that
ships attendance events.

- `CLSS_ATTENDANCE_GATEWAY_URL` - base URL of the events gateway.
- `clss.attendance.<env>.gateway_token` - gateway auth token (server-side).
- `clss.attendance.<env>.event_signing_key` - key used by the gateway to
  sign attendance event envelopes.
- `CLSS_ATTENDANCE_ENV` - deployment environment label (for example `dev`,
  `staging`, `prod`) used to resolve the namespaced secrets above.

No secret value is ever committed; configure these in the environment.

## Tests

```
pytest
```

The suite is import-safe and passes with **no network and no DB**. It
covers: capture never auto-finalises; risk detects consecutive / chronic /
pattern; reconciliation flags conflicts; staff substitution triggers only
after human confirmation; events are immutable and PII-free; and the
offline end-to-end shape.
