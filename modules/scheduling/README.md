# Classess School — Scheduling & continuity (B2)

The operational backbone that keeps teaching continuous: the academic calendar,
the dynamic timetable, the substitution ladder, pacing protection, and teacher
knowledge transfer. A capability module over the secure core.

Two non-negotiables run through every surface here:

- **Human authority.** The constraint solver and the substitution ladder
  produce **scored / ranked options for a human to approve** — they never
  auto-commit. Changing a live timetable or assigning a substitute is
  consequential and sits at `execute_with_permission` on the permission ladder;
  it waits for an explicit approval decision and is applied by a separate call.
- **Never a free period.** The substitution ladder is exhaustive (Level 1-6) so
  "leave it free" is never an option. The last resort is a **supervised**
  combine / study room under a duty teacher.

## What it owns

| File | Responsibility |
| --- | --- |
| `app/calendar.py` | The academic calendar — terms, holidays, the weekly instructional pattern, and dated overrides. Board-agnostic. Honest **working-day math** (in-term, instructional weekday, not a holiday; a working-override wins) — the denominator pacing reads. |
| `app/timetable.py` | The dynamic timetable + the **constraint solver**. Classifies every rule **hard / soft / contextual** (hard breach disqualifies; soft breach costs score; contextual applies only when its condition holds), generates candidate changes, and returns **scored alternatives** with evidence, confidence, owner, consequence, and a why-line. Never commits; `apply_change` is a separate call that refuses without a human approver. |
| `app/substitution.py` | The **substitution ladder** Level 1-6 (same-subject free → same-grade subject → any qualified free → departmental → general staff → supervised combine). Produces **ranked, scored, supervised** options; `is_free_period` is structurally `False`. `assign_substitute` refuses without a human approver. |
| `app/pacing.py` | **Pacing protection** — planned vs delivered periods, drift bands (`on_track` / `slipping` / `behind` / `at_risk` / `ahead`) against the working-day denominator (so holidays never read as behind). Plus the **teacher knowledge-transfer** handover note (where the class is, what is next, what to watch for) — opaque refs only. |
| `app/recovery.py` | **Pacing recovery + period swapping** — recommends recovery (add period / revision block / reallocate slot / period swap) for a drifting plan; proposes and (separately, human-gated) applies a time-neutral **period swap**; the bounded **low-risk-automation-within-policy** path auto-applies only a time-neutral swap that clears every explicit policy bound. |
| `app/optimisation.py` | The calendar's **continuous-optimisation** loop. Quantifies **instructional time lost** when an exception is declared mid-term (the working-day denominator shrinks), **re-projects** whether each section+subject plan still finishes the term against the revised remaining working days (`fits` / `tight` / `overruns`), and **recommends** a calendar-level response — a compensatory working day, or a re-pace — scored for human approval. Never reshapes the calendar; `apply_calendar_recovery` is the separate, human-gated step that appends a `working_override`. |
| `app/events.py` | Emits `timetable.changed`, `attendance.trigger`, and `pacing.drift_flagged` on the attributed, append-only event envelope (`operations` purpose). Opaque ids only; `timetable.changed` refuses to record an unapproved change. |
| `app/config.py` | Env-var **NAMES only**. Degrades gracefully when nothing is set. |

## Invariants honoured

- **Opaque identity only (INVARIANT 1 + 2).** Every event and handover note is
  keyed by `canonical_uuid` and opaque period/section/subject/ontology ids. No
  builder accepts a name/email; payloads carry no PII fields.
- **Append-only events (INVARIANT 5).** The emitter only appends; it never
  updates or deletes.
- **Every cross-service call passes the gateway.** Event egress is never direct;
  with no gateway + sink configured it degrades to a clearly-labelled in-memory
  append-only sink.
- **Permission ladder (INVARIANT 8).** Timetable changes and substitute
  assignments never auto-fire — they are scored/ranked for approval and applied
  only after an explicit human decision. Agents hold no credentials and cannot
  self-approve.
- **Secrets are env-only (INVARIANT 4).** No secret value is read at import or
  stored as a literal; only the dotted NAMES below are referenced.

## Configuration (environment variable NAMES only)

Dotted convention `clss.<app>.<env>.<purpose>`; the OS key is the dotted name
uppercased with dots/dashes → underscores (e.g.
`clss.scheduling.dev.gateway_url` → `CLSS_SCHEDULING_DEV_GATEWAY_URL`). All are
optional; absence keeps the module in deterministic, in-memory mode.

| Dotted name | OS env var | Purpose |
| --- | --- | --- |
| `clss.scheduling.dev.gateway_url` | `CLSS_SCHEDULING_DEV_GATEWAY_URL` | The only egress. Every cross-service call passes the gateway. |
| `clss.scheduling.dev.event_sink_url` | `CLSS_SCHEDULING_DEV_EVENT_SINK_URL` | Where emitted events are POSTed (through the gateway). |
| `clss.scheduling.dev.database_url` | `CLSS_SCHEDULING_DEV_DATABASE_URL` | The operational store (calendar, timetable rows). |
| `clss.scheduling.dev.workflow_url` | `CLSS_SCHEDULING_DEV_WORKFLOW_URL` | The A5 workflow engine that carries options to a human for approval. |

No secret VALUE is ever hardcoded. The gateway bearer token is read from the
environment by name at the point of egress (not implemented while no provider
exists); it is never exposed to the browser and never a `NEXT_PUBLIC_` var.

## Tests

```
pytest          # from this directory
```

Import-safe and offline: the whole suite runs with no network, no DB, and no
provider, exercising the deterministic (degraded) paths — the supported paths
until the gateway, event store, and workflow engine are wired.
