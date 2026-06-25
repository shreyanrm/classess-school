# Classess School — Teacher growth (B10)

Private, evidence-based teacher coaching over the secure core. It turns a
lesson's interaction signals into gentle, growth-oriented reflection that
surfaces to the teacher first, runs a human-owned quality-review workflow, and
carries a teacher's hard-won classroom knowledge forward when a class changes
hands.

Three stances run through every surface here and are enforced in code, not just
documented:

- **Teacher-first and private.** Coaching signals are private to the teacher by
  default. They widen audience only with the teacher's own consent ref; nothing
  pushes a signal to a principal or an open board.
- **No automated punitive ranking.** There is no code path that ranks teachers,
  builds a league table, or assigns a punitive auto-rating. The prohibition is a
  callable contract (`refuse_punitive_ranking`) that always refuses.
- **Employment decisions require human review.** Coaching describes a lesson and
  suggests one next step. Consequential decisions about a person are a
  human-owned review with an explicit human sign-off; the AI never decides.

## What it owns

| File | Responsibility |
| --- | --- |
| `app/interaction.py` | Classroom-interaction analysis from a lesson's delivery/engagement events. Deterministic metrics: **talk ratio**, **questioning quality** (higher- vs lower-order), **equity of voice** (participation evenness), **wait time** (the thinking gap). Descriptive lesson metrics, never a score on a person. Opaque speaker refs only. |
| `app/coaching.py` | Private, teacher-first **coaching signals** built from those metrics. Growth-framed: a reading, ONE optional next step, the evidence, a confidence band, and the audience guarantee. Refuses to construct a public signal; `refuse_punitive_ranking` and `employment_decision_guard` make the prohibitions hard errors. |
| `app/growth_plan.py` | The longitudinal layer: a private **development plan** built from a teacher's OWN signals over many lessons (per-dimension **trajectory** — improving / steady / slipping — plus growth-framed focus areas), and the **de-identified leadership aggregate**. The aggregate carries NO teacher refs and NO per-teacher rows (only cohort distributions), is built only from plans already **surfaced to their teacher** (coaching-first), and refuses below a **k-anonymity floor** of 5. `refuse_per_teacher_leadership_view` makes "show leadership a named teacher" a hard error. |
| `app/quality_review.py` | The human-owned **quality-review workflow** (`draft → teacher_reflection → reviewer_review → awaiting_sign_off → closed`). The teacher reflects first; a human reviewer signs off last; `auto_finalise` always refuses. Findings must link evidence; a coaching signal enters only with the teacher's consent. |
| `app/continuity.py` | The **knowledge-transfer / handover note** that travels with a class on a change of hands (leave, substitution, transfer, mentor rotation). Curriculum position + generic pedagogy + opaque refs only; a private coaching reflection travels only with the outgoing teacher's consent. |
| `app/events.py` | Emits `coaching.signal_generated` and `growth.plan_updated` (**both always private + teacher-first**), `quality.review_signed_off` (requires a human ref), and `continuity.handover_recorded` on the attributed, append-only event envelope (`growth` purpose). Opaque ids only; the plan event carries the *shape* (lessons observed + focus dimensions), never the trajectory verdict, a score, or a rank. |
| `app/config.py` | Env-var **NAMES only**. Degrades gracefully when nothing is set. Coaching visibility is a fixed product invariant, not a configurable secret. |

## Invariants honoured

- **Opaque identity only (INVARIANT 1 + 2).** Every metric, signal, review, note,
  and event is keyed by `canonical_uuid` and opaque teacher/reviewer/section/
  subject/lesson ids. No builder accepts a name/email; payloads carry no PII.
- **Append-only events (INVARIANT 5).** The emitter only appends; it never
  updates or deletes.
- **Consent gates cross-context reads (INVARIANT 6).** Coaching signals are
  private; they enter a review or a handover only with the teacher's explicit
  consent ref. Coaching events are stamped `private` + `teacher_first`.
- **Permission ladder / human authority (INVARIANT 8).** No automated punitive
  ranking is produced; a quality review is finalised only by an explicit human
  sign-off; the AI never makes an employment decision. Agents hold no credentials
  and cannot self-approve.
- **Every cross-service call passes the gateway.** Event egress is never direct;
  with no gateway + sink configured it degrades to a clearly-labelled in-memory
  append-only sink.
- **Secrets are env-only (INVARIANT 4).** No secret value is read at import or
  stored as a literal; only the dotted NAMES below are referenced.

## Configuration (environment variable NAMES only)

Dotted convention `clss.<app>.<env>.<purpose>`; the OS key is the dotted name
uppercased with dots/dashes → underscores (e.g.
`clss.teachergrowth.dev.gateway_url` → `CLSS_TEACHERGROWTH_DEV_GATEWAY_URL`). All
are optional; absence keeps the module in deterministic, in-memory mode.

| Dotted name | OS env var | Purpose |
| --- | --- | --- |
| `clss.teachergrowth.dev.gateway_url` | `CLSS_TEACHERGROWTH_DEV_GATEWAY_URL` | The only egress. Every cross-service call passes the gateway. |
| `clss.teachergrowth.dev.event_sink_url` | `CLSS_TEACHERGROWTH_DEV_EVENT_SINK_URL` | Where emitted growth events are POSTed (through the gateway). |
| `clss.teachergrowth.dev.database_url` | `CLSS_TEACHERGROWTH_DEV_DATABASE_URL` | The operational store (review records, handover notes). |
| `clss.teachergrowth.dev.workflow_url` | `CLSS_TEACHERGROWTH_DEV_WORKFLOW_URL` | The A5 workflow engine that routes a quality review to a human reviewer. |

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
