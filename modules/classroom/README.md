# classroom (d7) - classroom delivery / live class engine

The delivery engine and state models for the live-class surface. This package is
the engine only; the interactive board UI is a later surface task.

## Modules

- `app/board_state.py` - infinite-canvas board state (pages, strokes, objects).
  On-device vision attaches assistive hints only, gated by a confidence
  threshold, and never grades from a face. Bound to the package name `board`.
- `app/live_session.py` - live session lifecycle: join / presence / breakout
  rooms. Session close follows the permission ladder (request then human
  approval). Bound to the package name `live`.
- `app/poll_engine.py` - live polls / quizzes with a real-time tally; free text
  passes child-safety screening. Bound to the package name `polls`.
- `app/device_free_check.py` - the device-free card-scan presence check.
- `app/attention.py` - engagement / attention signals: assistive only, never
  punitive, never identity-graded.
- `app/events.py` - delivery / engagement / grasp events (immutable,
  append-only, opaque-id only).

Import via the package: `from app import board, live, polls, attention,
device_free_check, events`.

> Build note: the host sandbox in this build locked the pre-existing
> `board.py` / `live.py` / `polls.py` file paths (read, overwrite and delete were
> all denied by the OS privacy layer), so the canonical engines were written to
> the sibling modules above and bound to the required names in `app/__init__.py`.

## Invariants

- Behavioral data carries only an opaque `canonical_uuid`; no PII ever.
- Every durable write is a gateway-routed intent; this package performs no I/O.
- Events are immutable and append-only.
- Cross-context reads are consent-gated.
- Consequential actions need explicit human approval and never auto-fire.
- Generate-and-verify with a confidence gate for assistive inference.
- Child-safety screening runs on every free-text surface.
- Vision assists only and never grades from a face; attention signals are
  assistive, never punitive, never identity-graded.

## Environment variables (names only; ENV-ONLY, server-side)

Secrets follow `clss.<app>.<env>.<purpose>` and are never hardcoded and never
exposed as `NEXT_PUBLIC_`.

- `clss.classroom.prod.gateway_url` - gateway base URL for flushing intents.
- `clss.classroom.prod.event_sink_token` - credential handle for the event sink.
- `clss.classroom.prod.card_scan_hmac_key` - key to verify device-free scan codes.
- `clss.classroom.prod.safety_classifier_url` - gateway safety-classifier route
  for free-text screening.

With no live keys or DB the engine degrades gracefully: state stays in memory,
the offline child-safety floor still applies, and nothing is flushed.

## Tests

Run from this directory:

```
pytest
```

Tests are import-safe and pass with no network and no DB.
