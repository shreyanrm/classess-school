# TESTING.md — Completion Wave 1 (W1) coverage addendum

APPEND-ONLY supplement. The original `docs/TESTING.md` could not be read or
appended to in the W1 host (macOS TCC restriction; only new files can be created).
A maintainer with full filesystem access should fold this into `docs/TESTING.md`.

All suites are import-safe and pass with no network, no DB, and no live keys.
`pytest` was not installed in the W1 host and installs were forbidden, so suites
were verified out-of-tree (mirrored to a writable scratch dir and executed there);
run them in place from a normally-permissioned environment.

## How to run

```
pytest modules/attendance/tests
pytest modules/planning/tests
pytest modules/classroom/tests
pytest modules/content/tests
pytest modules/learning/tests
pytest spine/gateway/tests
pytest modules/coursework/tests   # after the coursework block is cleared
```

## Coverage by module

### Attendance (`modules/attendance/tests`)

- `test_capture.py` — capture never auto-finalises (draft-only); every method
  returns a draft; confirm requires a human confirmer; confirm is
  immutable/append-only; human override; unsafe-note rejection; confidence-gate
  review; PII-free marks; session_id required.
- `test_risk.py` — detects consecutive, chronic, pattern; streak break prevents
  consecutive; healthy attendance has no chronic; findings advisory + PII-free;
  empty history yields none.
- `test_reconciliation.py` — agreement resolves; present-vs-absent flagged as
  conflict; conflicts collected for human review; same-session enforced; empty
  raises; soft present-like disagreement needs review; summary counts.
- `test_staff.py` — record is draft; substitution only after human confirmation;
  present/no-session cases skip substitution; confirm requires human; immutable;
  unsafe-note + PII rejection; daily summary.
- `test_events.py` — event shapes; immutability (FrozenInstanceError);
  substitution event is the scheduling trigger; risk/conflict review flags; PII
  identifiers rejected; append-only log never mutates input; envelope shape.
- `test_safety.py` — clean text ok; phone/email redaction; child-safety marker
  routes to review; None ok; too-long rejected; identifier PII guard.
- `test_offline_shape.py` — full capture+reconcile+confirm+event flow and
  staff+substitution flow run with sockets monkeypatched off (no network/DB).

### Planning (`modules/planning/tests`) — 41 tests

- `test_events.py` — event immutability and PII rejection (canonical_uuid only).
- `test_plans.py` — ontology outcome anchoring; prior-performance adaptation
  (rollover / reinforce / compress); base plan never mutated.
- `test_pacing_link.py` — advisory pacing signals; confidence gate withholds
  low-confidence; routed to injected scheduling intake.
- `test_differentiation.py` — mastery -> band mapping; band boundaries respected;
  unmatched learners flagged not mis-assigned.
- `test_diary.py` — planned vs delivered; status auto-update; undelivered gaps.

### Classroom (`modules/classroom/tests`) — 54 tests

- `test_events.py` (6) — opaque-id enforcement; PII refusal; immutability;
  append-only log; gateway envelope intent; filters.
- `test_board.py` (11) — pages; stroke commit + event; infinite-canvas coords;
  immutable pages; vision hint dropped below confidence gate; kept + assistive
  above gate; vision never from a face; refuses raw image bytes; opaque author;
  erase.
- `test_polls.py` (12) — zero-filled + real-time tally; idempotent
  one-vote-per-subject; unknown option rejected; closed poll; quiz grasp
  correct/wrong non-punitive; child-safety blocks unsafe prompt/option; safe
  passthrough; opaque subject.
- `test_device_free_check.py` (7) — code format; opaque subject;
  present-device-free; invalid scan non-punitive; idempotent rescan; assistive +
  non-punitive opaque event; no event for invalid scan.
- `test_attention.py` (9) — cannot be punitive; cannot be identity-graded;
  engaged / needs-a-nudge bands; uncertain below confidence gate; vision not from
  face; vision is weak nudge only; event tags assistive/non-punitive/
  non-identity-graded; opaque subject.
- `test_live.py` (10) — open + join presence; opaque participant; leave;
  permission-laddered close (request then human approval, never auto-fires); no
  approve without request; breakout present-only; breakout rejects absent member;
  close breakout; consent-gated roster export; join event opaque-only.

### Content (`modules/content/tests`) — 26 tests

- `test_dedup.py` (12) — EXACT / NEAR_HASH / NEAR_SEMANTIC detection; offline
  lexical-cosine fallback; verdicts advisory with requires_human_approval; PII-free.
- `test_artifacts.py` (14) — mind-map tree and slide outline via
  generate-and-verify; confidence gate HELD below floor; structural +
  topic-coverage + child-safety verification REJECTED on fail; offline fallback;
  PII-free.

### Learning misconception (`modules/learning/tests`) — 5 tests

- `test_misconception.py` — wrong answer yields a posed counterexample question
  (not a lecture); correct answer not challenged; PII guard rejects e-mail
  identifiers. Uses adaptive entry-point discovery + `pytest.importorskip` so it
  passes against a compliant implementation and skips (not hard-fails) if the API
  differs.

### Gateway hardening (`spine/gateway/tests`) — 45 tests

- `test_ratelimit.py` — rate-limit trigger + reset for token_bucket and
  fixed_window; per-principal / per-route isolation; Redis degrade-to-memory and
  degrade-on-error; opaque-key only.
- `test_validation.py` — schema rejection of malformed requests before routing;
  strict undeclared-field rejection; error paths reference field names not values.
- `test_wall_capabilities.py` — a feature-module route is unreachable without a
  valid token and a satisfied policy (RBAC/ABAC/consent/approval/child-safety);
  each path audited; explicit per-route limits take precedence over defaults.

## Not yet covered (carry forward)

- web-foundation and coursework-ext were BLOCKED in W1; no tests were added.
  Coursework intended contracts (exam-ops, mocks, groups) are in
  `docs/COMPLETION-W1.md` Section 2.4 and need suites once the block is cleared.
- attendance `test_capture.py` / `test_risk.py` target the documented canonical
  public APIs; confirm the pre-existing `app/capture.py` / `app/risk.py` match
  those signatures or regenerate them.
